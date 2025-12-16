import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../utils/api';
import { useSSE } from '../hooks/useSSE';
import type { TaskStatus } from '../types/api';

export default function TasksPage() {
  const navigate = useNavigate();
  // Автоматическое переключение задач отключено - taskIdParam больше не используется

  const [tasks, setTasks] = useState<TaskStatus[]>([]);
  const [selectedTask, setSelectedTask] = useState<TaskStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('');
  const [error, setError] = useState<string | null>(null);

  const { event, isConnected } = useSSE(selectedTask?.request_id || null);

  useEffect(() => {
    loadTasks();
    const interval = setInterval(loadTasks, 5000);
    return () => clearInterval(interval);
  }, [filter]);

  // УБРАНО АВТОМАТИЧЕСКОЕ ПЕРЕКЛЮЧЕНИЕ - задача загружается только при явном клике пользователя
  // useEffect(() => {
  //   if (taskIdParam && (!selectedTask || selectedTask.request_id !== taskIdParam)) {
  //     loadTask(taskIdParam);
  //   }
  // }, [taskIdParam]);

  useEffect(() => {
    // ОБНОВЛЯЕМ ТОЛЬКО выбранную задачу при SSE событиях, НИКОГДА не переключаемся
    if (event && selectedTask) {
      if (event.type === 'progress' || event.type === 'completed') {
        // СТРОГАЯ ПРОВЕРКА: обновляем ТОЛЬКО если это событие для ВЫБРАННОЙ задачи
        const eventRequestId = event.data?.request_id || event.data?.status?.request_id || event.data?.request_id;
        // ОБЯЗАТЕЛЬНО проверяем, что request_id совпадает, иначе ИГНОРИРУЕМ
        if (eventRequestId && eventRequestId === selectedTask.request_id) {
          // Обновляем данные выбранной задачи, НЕ переключаемся
        loadTask(selectedTask.request_id);
        }
        // ВСЕ остальные события ИГНОРИРУЕМ - НЕ переключаемся автоматически
      }
    }
  }, [event, selectedTask]);

  const loadTasks = async () => {
    try {
      setError(null);
      const data = await apiClient.tasks.list(50, 0, filter || undefined);
      setTasks(data);
      
      // КРИТИЧЕСКИ ВАЖНО: ОБНОВЛЯЕМ ТОЛЬКО выбранную задачу, НИКОГДА не переключаемся
      // НИ ПРИ КАКИХ УСЛОВИЯХ не выбираем задачу автоматически
      if (selectedTask) {
        const updatedTask = data.find((t) => t.request_id === selectedTask.request_id);
        if (updatedTask) {
          // Обновляем только статус и прогресс, сохраняем тесты и метрики
          // НЕ меняем selectedTask на другую задачу
          setSelectedTask({
            ...updatedTask,
            tests: selectedTask.tests || updatedTask.tests,
            metrics: selectedTask.metrics || updatedTask.metrics
          });
        }
        // Если выбранной задачи нет в списке - НЕ переключаемся, оставляем как есть
      }
      // КРИТИЧЕСКИ ВАЖНО: НИКОГДА не выбираем первую задачу автоматически
      // НИКОГДА не выбираем задачу с taskIdParam автоматически
      // НИКОГДА не выбираем задачу по статусу автоматически
    } catch (error: any) {
      console.error('Error loading tasks:', error);
      // Показываем пользователю понятное сообщение об ошибке
      if (error.code === 'ERR_NETWORK' || error.message?.includes('Network Error') || error.message?.includes('Connection reset')) {
        setError('Не удалось подключиться к серверу. Проверьте, что API Gateway запущен на порту 8000.');
      } else {
        setError(error.response?.data?.detail || error.message || 'Ошибка загрузки задач');
      }
    } finally {
      setLoading(false);
    }
  };

  const loadTask = async (requestId: string) => {
    try {
      const task = await apiClient.tasks.get(requestId, true, true);
      if (task) {
        setSelectedTask(task);
        setTasks((prev) => {
          const existingIndex = prev.findIndex((t) => t.request_id === requestId);
          if (existingIndex >= 0) {
            const updated = [...prev];
            updated[existingIndex] = task;
            return updated;
          } else {
            return [task, ...prev];
          }
        });
      }
    } catch (error) {
      console.error('Error loading task:', error);
    }
  };

  const handleResume = async (requestId: string) => {
    try {
      await apiClient.tasks.resume(requestId);
      loadTask(requestId);
    } catch (error: any) {
      const errorMsg = error.code === 'ERR_NETWORK' || error.message?.includes('Network Error')
        ? 'Не удалось подключиться к серверу. Проверьте, что API Gateway запущен.'
        : error.response?.data?.detail || 'Ошибка возобновления задачи';
      setError(errorMsg);
    }
  };

  const getStatusBadge = (status: string) => {
    const statusMap: Record<string, string> = {
      pending: 'status-pending',
      started: 'status-processing',
      reconnaissance: 'status-processing',
      generation: 'status-processing',
      validation: 'status-processing',
      optimization: 'status-processing',
      completed: 'status-success',
      failed: 'status-error',
    };
    return statusMap[status] || 'status-default';
  };

  if (loading && tasks.length === 0) {
    return <div className="page">Загрузка...</div>;
  }

  return (
    <div className="page">
      <div className="page-header">
        <h2>Управление задачами</h2>
        <p>Мониторинг и управление задачами генерации тестов</p>
      </div>

      {error && (
        <div className="error-message" style={{ 
          padding: '1rem', 
          margin: '1rem 0', 
          backgroundColor: '#fee', 
          border: '1px solid #fcc', 
          borderRadius: '4px',
          color: '#c33'
        }}>
          <strong>Ошибка:</strong> {error}
          <button 
            onClick={() => setError(null)} 
            style={{ marginLeft: '1rem', padding: '0.25rem 0.5rem', cursor: 'pointer' }}
          >
            ✕
          </button>
        </div>
      )}

      <div className="tasks-layout">
        <div className="tasks-list">
          <div className="filter-group">
            <select value={filter} onChange={(e) => setFilter(e.target.value)}>
              <option value="">Все статусы</option>
              <option value="pending">Ожидание</option>
              <option value="processing">В процессе</option>
              <option value="completed">Завершено</option>
              <option value="failed">Ошибка</option>
            </select>
          </div>

          <div className="task-cards">
            {tasks.map((task) => (
              <div
                key={task.request_id}
                className={`task-card ${selectedTask?.request_id === task.request_id ? 'active' : ''}`}
                onClick={() => {
                  setSelectedTask(task);
                  // Убрали navigate - не переключаем URL при клике на задачу
                }}
              >
                <div className="task-card-header">
                  <span className={`status-badge ${getStatusBadge(task.status)}`}>
                    {task.status}
                  </span>
                  <span className="task-id">{task.request_id.slice(0, 8)}...</span>
                </div>
                {task.current_step && (
                  <div className="task-step">Шаг: {task.current_step}</div>
                )}
                {task.progress !== undefined && (
                  <div className="progress-bar">
                    <div
                      className="progress-fill"
                      style={{ width: `${task.progress}%` }}
                    />
                  </div>
                )}
                {task.result_summary && (
                  <div className="task-summary">
                    Тестов: {task.result_summary.tests_generated || 0}
                  </div>
                )}
                {task.error_message && (
                  <div className="task-error">{task.error_message}</div>
                )}
              </div>
            ))}
          </div>
        </div>

        {selectedTask && (
          <div className="task-details">
            <div className="task-details-header">
              <h3>Детали задачи</h3>
              <button
                onClick={() => {
                  setSelectedTask(null);
                  navigate('/tasks');
                }}
                className="btn-secondary"
              >
                Закрыть
              </button>
            </div>

            <div className="detail-section">
              <div className="detail-item">
                <strong>ID:</strong> {selectedTask.request_id}
              </div>
              <div className="detail-item">
                <strong>Статус:</strong>{' '}
                <span className={`status-badge ${getStatusBadge(selectedTask.status)}`}>
                  {selectedTask.status}
                </span>
              </div>
              {selectedTask.current_step && (
                <div className="detail-item">
                  <strong>Текущий шаг:</strong> {selectedTask.current_step}
                </div>
              )}
              {selectedTask.progress !== undefined && (
                <div className="detail-item">
                  <strong>Прогресс:</strong> {selectedTask.progress}%
                  <div className="progress-bar">
                    <div
                      className="progress-fill"
                      style={{ width: `${selectedTask.progress}%` }}
                    />
                  </div>
                </div>
              )}
              {selectedTask.started_at && (
                <div className="detail-item">
                  <strong>Начато:</strong> {new Date(selectedTask.started_at).toLocaleString('ru')}
                </div>
              )}
              {selectedTask.completed_at && (
                <div className="detail-item">
                  <strong>Завершено:</strong> {new Date(selectedTask.completed_at).toLocaleString('ru')}
                </div>
              )}
              {isConnected && (
                <div className="detail-item">
                  <strong>SSE:</strong> <span className="status-success">Подключено</span>
                </div>
              )}
            </div>

            {selectedTask.result_summary && (
              <div className="detail-section">
                <h4>Результаты</h4>
                <div className="detail-item">
                  <strong>Сгенерировано тестов:</strong> {selectedTask.result_summary.tests_generated || 0}
                </div>
                <div className="detail-item">
                  <strong>Валидировано:</strong> {selectedTask.result_summary.tests_validated || 0}
                </div>
                <div className="detail-item">
                  <strong>Оптимизировано:</strong> {selectedTask.result_summary.tests_optimized || 0}
                </div>
              </div>
            )}

            {selectedTask.tests && selectedTask.tests.length > 0 && (
              <div className="detail-section">
                <h4>Тесты ({selectedTask.tests.length})</h4>
                <div className="tests-list">
                  {selectedTask.tests.map((test) => (
                    <div 
                      key={test.test_id} 
                      className="test-item"
                      onClick={(e) => {
                        // Предотвращаем всплытие события, чтобы не срабатывал onClick на родительских элементах
                        e.stopPropagation();
                      }}
                    >
                      <div className="test-name">{test.test_name}</div>
                      <div className="test-meta">
                        <span className="test-type">{test.test_type}</span>
                        {test.priority && <span className="test-priority">Приоритет: {test.priority}</span>}
                      </div>
                      {test.test_code && (
                        <details className="test-code" onClick={(e) => e.stopPropagation()}>
                          <summary>Код теста</summary>
                          <pre>{test.test_code}</pre>
                        </details>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {selectedTask.error_message && (
              <div className="detail-section">
                <h4>Ошибка</h4>
                <div className="error-message">{selectedTask.error_message}</div>
                {selectedTask.status === 'failed' && (
                  <button
                    onClick={() => handleResume(selectedTask.request_id)}
                    className="btn-primary"
                  >
                    Возобновить задачу
                  </button>
                )}
              </div>
            )}

            {selectedTask.metrics && selectedTask.metrics.length > 0 && (
              <div className="detail-section">
                <h4>Метрики</h4>
                <table className="metrics-table">
                  <thead>
                    <tr>
                      <th>Агент</th>
                      <th>Длительность (мс)</th>
                      <th>Статус</th>
                      <th>Токены LLM</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedTask.metrics.map((metric, index) => (
                      <tr key={index}>
                        <td>{metric.agent_name}</td>
                        <td>{metric.duration_ms}</td>
                        <td>{metric.status}</td>
                        <td>{metric.llm_tokens_total || '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

