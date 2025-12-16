
from typing import Dict, Any, Optional
from datetime import datetime
import uuid
try:
    from langgraph.graph import StateGraph, END
    try:
        from langgraph.checkpoint.postgres import PostgresSaver
    except ImportError:
        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver as PostgresSaver
        except ImportError:
            from langgraph.checkpoint.memory import MemorySaver as PostgresSaver
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    StateGraph = None
    END = None
    PostgresSaver = None
from shared.utils.database import get_db
from shared.models.database import Request
from shared.config.settings import settings
from shared.utils.redis_client import redis_client
from shared.utils.logger import agent_logger
from .state import WorkflowState
from .nodes import (
    reconnaissance_node,
    generation_node,
    validation_node,

    save_results_node,
    should_retry_generation
)
class LangGraphWorkflow:
    def __init__(self):
        if not LANGGRAPH_AVAILABLE:
            raise ImportError("LangGraph is not installed. Install with: pip install langgraph langchain")
        try:
            if hasattr(PostgresSaver, 'from_conn_string'):
                self.checkpointer = PostgresSaver.from_conn_string(settings.langgraph_checkpoint)
            elif hasattr(PostgresSaver, 'from_conn'):
                from sqlalchemy import create_engine
                engine = create_engine(settings.langgraph_checkpoint)
                self.checkpointer = PostgresSaver(engine)
            else:
                self.checkpointer = PostgresSaver()
                agent_logger.warning("Using MemorySaver - checkpoints will not persist")
        except Exception as e:
            agent_logger.error(f"Error creating checkpointer: {e}", exc_info=True)
            try:
                from langgraph.checkpoint.memory import MemorySaver
                self.checkpointer = MemorySaver()
                agent_logger.warning("Falling back to MemorySaver")
            except:
                raise ImportError("Cannot create checkpointer. Install langgraph-checkpoint or langgraph.")
        self.graph = self._build_graph()
        self.app = self.graph.compile(checkpointer=self.checkpointer)
    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(WorkflowState)
        workflow.add_node("reconnaissance", reconnaissance_node)
        workflow.add_node("generation", generation_node)
        workflow.add_node("validation", validation_node)
        # ОПТИМИЗАЦИЯ УБРАНА - вызывает проблемы с зависанием
        # workflow.add_node("optimization", optimization_node)
        workflow.add_node("save_results", save_results_node)
        workflow.set_entry_point("reconnaissance")
        workflow.add_edge("reconnaissance", "generation")
        workflow.add_edge("generation", "validation")
        workflow.add_conditional_edges(
            "validation",
            should_retry_generation,
            {
                "retry": "generation",
                "continue": "save_results"  # Пропускаем оптимизацию, сразу сохраняем
            }
        )
        # workflow.add_edge("optimization", "save_results")  # Убрано
        workflow.add_edge("save_results", END)
        return workflow
    def run_workflow(
        self,
        request_id: str,
        url: str,
        requirements: list,
        test_type: str,
        options: dict = None,
        thread_id: Optional[str] = None
    ) -> Dict[str, Any]:
        options = options or {}
        if not thread_id:
            thread_id = f"thread_{request_id}"
        with get_db() as db:
            request = db.query(Request).filter(Request.request_id == uuid.UUID(request_id)).first()
            if not request:
                raise ValueError(f"Request {request_id} not found")
            request.langgraph_thread_id = thread_id
            request.status = "started"
            request.started_at = datetime.utcnow()
            db.commit()
        initial_state: WorkflowState = {
            "request_id": request_id,
            "url": url,
            "requirements": requirements,
            "test_type": test_type,
            "options": options,
            "page_structure": None,
            "generated_tests": [],
            "validated_tests": [],
            "optimized_tests": [],
            "current_step": "started",
            "error": None,
            "retry_count": 0
        }
        try:
            config = {"configurable": {"thread_id": thread_id}}
            # Используем stream для отслеживания прогресса и предотвращения зависаний
            try:
                final_state = None
                last_node = None
                nodes_visited = []
                
                # УПРОЩЕННАЯ ВЕРСИЯ: используем stream напрямую с таймаутом через invoke
                # Stream может зависать, поэтому используем invoke с таймаутом
                agent_logger.info(f"Starting workflow stream for {request_id}")
                
                # Пытаемся использовать stream, но с ограничением по времени
                import signal
                import threading
                
                stream_completed = threading.Event()
                stream_error = [None]
                final_state_from_stream = [None]
                
                def run_stream():
                    try:
                        for event in self.app.stream(initial_state, config):
                            for node_name, node_output in event.items():
                                last_node = node_name
                                nodes_visited.append(node_name)
                                if node_output and isinstance(node_output, dict):
                                    current_step = node_output.get("current_step", "")
                                    if current_step:
                                        agent_logger.info(
                                            f"Workflow progress for {request_id}: {node_name} -> {current_step}",
                                            extra={"request_id": request_id, "node": node_name, "step": current_step}
                                        )
                                    final_state_from_stream[0] = node_output
                                    # Публикуем прогресс в Redis
                                    redis_client.publish_event(
                                        f"request:{request_id}",
                                        {"status": "processing", "step": current_step, "node": node_name}
                                    )
                        stream_completed.set()
                    except Exception as e:
                        stream_error[0] = e
                        stream_completed.set()
                
                # Запускаем stream в отдельном потоке
                stream_thread = threading.Thread(target=run_stream, daemon=True)
                stream_thread.start()
                
                # Ждем завершения с таймаутом 10 минут
                if stream_completed.wait(timeout=600):
                    if stream_error[0]:
                        raise stream_error[0]
                    final_state = final_state_from_stream[0]
                else:
                    # Таймаут - используем invoke как fallback
                    agent_logger.warning(f"Stream timeout for {request_id}, using invoke")
                    final_state = self.app.invoke(initial_state, config)
                
                agent_logger.info(f"Stream completed for {request_id}, nodes_visited={nodes_visited}, last_node={last_node}, final_step={final_state.get('current_step') if final_state else 'None'}")
                
                # Если stream завершился, но не дошли до save_results, используем invoke как fallback
                if "save_results" not in nodes_visited:
                    agent_logger.warning(f"Stream did not reach save_results for {request_id}, using invoke as fallback. Nodes visited: {nodes_visited}")
                    # Пытаемся получить финальное состояние через invoke с таймаутом
                    import signal
                    def timeout_handler(signum, frame):
                        raise TimeoutError("Workflow invoke timeout")
                    signal.signal(signal.SIGALRM, timeout_handler)
                    signal.alarm(300)  # 5 минут таймаут
                    try:
                        final_state = self.app.invoke(initial_state, config)
                        signal.alarm(0)  # Отменяем таймаут
                    except TimeoutError:
                        agent_logger.error(f"Workflow invoke timeout for {request_id}")
                        raise
            except Exception as stream_e:
                agent_logger.error(f"Workflow stream error: {stream_e}", exc_info=True)
                # Если stream упал, пытаемся получить финальное состояние через invoke
                try:
                    final_state = self.app.invoke(initial_state, config)
                except Exception as invoke_e:
                    agent_logger.error(f"Workflow invoke also failed: {invoke_e}", exc_info=True)
                    raise
            
            agent_logger.info(
                f"Workflow completed for request {request_id}",
                extra={"thread_id": thread_id, "step": final_state.get("current_step") if final_state else "unknown"}
            )
            return {
                "request_id": request_id,
                "thread_id": thread_id,
                "status": "completed",
                "step": final_state.get("current_step") if final_state else "unknown"
            }
        except Exception as e:
            agent_logger.error(f"Workflow error: {e}", exc_info=True)
            with get_db() as db:
                request = db.query(Request).filter(Request.request_id == uuid.UUID(request_id)).first()
                if request:
                    request.status = "failed"
                    request.error_message = str(e)
                    try:
                        from shared.utils.email_service import email_service
                        from shared.models.database import User
                        if request.user_id:
                            user = db.query(User).filter(User.user_id == request.user_id).first()
                            if user and user.email:
                                email_service.send_error_notification(
                                    to=user.email,
                                    request_id=str(request.request_id),
                                    error_message=str(e)
                                )
                    except Exception as email_error:
                        agent_logger.warning(f"Failed to send error email notification: {email_error}")
                    db.commit()
            redis_client.publish_event(
                f"request:{request_id}",
                {"status": "failed", "error": str(e)}
            )
            raise
    def resume_workflow(self, request_id: str) -> Dict[str, Any]:
        # Сохраняем thread_id до закрытия сессии, чтобы избежать ошибки "not bound to a Session"
        thread_id = None
        with get_db() as db:
            request = db.query(Request).filter(Request.request_id == uuid.UUID(request_id)).first()
            if not request:
                raise ValueError(f"Request {request_id} not found")
            if not request.langgraph_thread_id:
                raise ValueError(f"No thread_id found for request {request_id}. Cannot resume.")
            # Сохраняем значение атрибута до закрытия сессии
            thread_id = request.langgraph_thread_id
        agent_logger.info(f"Resuming workflow for request {request_id}, thread_id: {thread_id}")
        config = {"configurable": {"thread_id": thread_id}}
        try:
            # Используем checkpointer для получения состояния
            if hasattr(self.checkpointer, 'get'):
                try:
                    state = self.checkpointer.get(config)
                except Exception as e:
                    agent_logger.warning(f"Error getting checkpoint for thread_id {thread_id}: {e}. Starting new workflow.")
                    state = None
                if not state:
                    # Если checkpoint не найден, начинаем workflow заново
                    agent_logger.warning(f"No checkpoint found for thread_id {thread_id}. Starting new workflow instead of resuming.")
                    raise ValueError(f"No checkpoint found for thread_id {thread_id}. Please start a new workflow instead.")
                # Получаем последнее состояние из checkpoint
                if hasattr(state, 'values'):
                    current_state = state.values
                elif isinstance(state, dict) and 'values' in state:
                    current_state = state['values']
                elif isinstance(state, dict):
                    current_state = state
                else:
                    raise ValueError(f"Invalid checkpoint state format for thread_id {thread_id}")
            elif hasattr(self.app, 'get_state'):
                # Fallback на старый API, если доступен
                state = self.app.get_state(config)
                if not state or not state.values:
                    raise ValueError(f"No checkpoint found for thread_id {thread_id}")
                current_state = state.values
            else:
                raise ValueError(f"Cannot get state: checkpointer or app.get_state not available")
            with get_db() as db:
                request = db.query(Request).filter(Request.request_id == uuid.UUID(request_id)).first()
                if request:
                    request.status = "started"
                    db.commit()
            final_state = self.app.invoke(current_state, config)
            agent_logger.info(
                f"Workflow resumed and completed for request {request_id}",
                extra={"thread_id": thread_id, "step": final_state.get("current_step") if final_state else "unknown"}
            )
            return {
                "request_id": request_id,
                "thread_id": thread_id,
                "status": "completed",
                "step": final_state.get("current_step") if final_state else "unknown"
            }
        except Exception as e:
            agent_logger.error(f"Resume workflow error: {e}", exc_info=True)
            with get_db() as db:
                request = db.query(Request).filter(Request.request_id == uuid.UUID(request_id)).first()
                if request:
                    request.status = "failed"
                    request.error_message = str(e)
                    try:
                        from shared.utils.email_service import email_service
                        from shared.models.database import User
                        if request.user_id:
                            user = db.query(User).filter(User.user_id == request.user_id).first()
                            if user and user.email:
                                email_service.send_error_notification(
                                    to=user.email,
                                    request_id=str(request.request_id),
                                    error_message=str(e)
                                )
                    except Exception as email_error:
                        agent_logger.warning(f"Failed to send error email notification: {email_error}")
                    db.commit()
            redis_client.publish_event(
                f"request:{request_id}",
                {"status": "failed", "error": str(e)}
            )
            raise