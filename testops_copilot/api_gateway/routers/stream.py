
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
from uuid import UUID
import json
import asyncio
from typing import AsyncGenerator
from shared.utils.redis_client import redis_client
from shared.utils.database import SessionLocal
from shared.models.database import Request
from shared.utils.logger import api_logger
router = APIRouter(prefix="/stream", tags=["Streaming"])
async def event_generator(request_id: UUID) -> AsyncGenerator[str, None]:
    channel = f"request:{request_id}"
    # Проверяем существование request ДО создания соединений
    db = SessionLocal()
    try:
        request = db.query(Request).filter(Request.request_id == request_id).first()
        if not request:
            yield {"event": "error", "data": json.dumps({'error': 'Request not found'})}
            return
    finally:
        db.close()
    
    pubsub = None
    redis_conn = None
    try:
        pubsub, redis_conn = await redis_client.subscribe_channel_async(channel)
        last_heartbeat = asyncio.get_event_loop().time()
        
        while True:
            try:
                message = await asyncio.wait_for(pubsub.get_message(ignore_subscribe_messages=True), timeout=1.0)
                if message and message['type'] == 'message':
                    try:
                        data = json.loads(message['data'])
                        # Определяем тип события на основе данных
                        if data.get('step') == 'completed' or data.get('status') == 'completed':
                            # Используем формат для sse_starlette: словарь с event и data
                            yield {"event": "completed", "data": json.dumps(data)}
                            # Даем время на отправку перед закрытием
                            await asyncio.sleep(0.1)
                            break
                        elif data.get('error') or data.get('status') == 'failed':
                            # Для ошибок отправляем событие типа 'error'
                            error_data = data if isinstance(data, dict) else {'error': str(data)}
                            yield {"event": "error", "data": json.dumps(error_data)}
                            await asyncio.sleep(0.1)
                            break
                        else:
                            # Для прогресса отправляем событие типа 'progress'
                            yield {"event": "progress", "data": json.dumps(data)}
                    except json.JSONDecodeError as json_err:
                        # Логируем и пропускаем некорректные сообщения
                        api_logger.warning(f"Invalid JSON in Redis message: {message['data']}, error: {json_err}")
                        continue
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                # Логируем и отправляем ошибку клиенту
                yield {"event": "error", "data": json.dumps({'error': f'Stream error: {str(e)}'})}
                break
            
            current_time = asyncio.get_event_loop().time()
            if current_time - last_heartbeat >= 30:
                # Heartbeat - отправляем пустое сообщение для поддержания соединения
                try:
                    yield ":heartbeat\n\n"
                except Exception as heartbeat_err:
                    api_logger.warning(f"Heartbeat send error: {heartbeat_err}")
                    break
                last_heartbeat = current_time
            
            await asyncio.sleep(0.1)
    except Exception as e:
        # Убеждаемся, что клиент получает информацию об ошибке
        try:
            error_message = str(e)
            # Убеждаемся, что сообщение об ошибке валидное JSON
            error_data = {'error': error_message, 'status': 'failed'}
            yield {"event": "error", "data": json.dumps(error_data)}
        except Exception as json_err:
            # Если даже JSON не удалось создать, отправляем простой текст
            try:
                yield {"event": "error", "data": json.dumps({'error': 'Stream connection error'})}
            except:
                pass
    finally:
        # Корректно закрываем соединения
        if pubsub:
            try:
                await pubsub.unsubscribe(channel)
                await pubsub.close()
            except:
                pass
        if redis_conn:
            try:
                await redis_conn.close()
            except:
                pass
@router.get("/{request_id}")
async def stream_events(request_id: UUID):
    from shared.utils.database import SessionLocal
    db = SessionLocal()
    try:
        request = db.query(Request).filter(Request.request_id == request_id).first()
        if not request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Request with ID {request_id} not found"
            )
    finally:
        db.close()
    return EventSourceResponse(
        event_generator(request_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )