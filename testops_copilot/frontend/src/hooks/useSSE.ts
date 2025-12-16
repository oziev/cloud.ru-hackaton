import { useEffect, useRef, useState } from 'react';
import { apiClient } from '../utils/api';

export interface SSEEvent {
  type: 'progress' | 'completed' | 'error';
  data: any;
}

export function useSSE(requestId: string | null) {
  const [event, setEvent] = useState<SSEEvent | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!requestId) {
      return;
    }

    const url = apiClient.stream.getUrl(requestId);
    const eventSource = new EventSource(url);

    eventSource.onopen = () => {
      setIsConnected(true);
    };

    // Обработка обычных сообщений (без явного типа события)
    eventSource.onmessage = (e) => {
      try {
        // Проверяем, что данные есть
        if (!e.data || !e.data.trim()) {
          return;
        }
        
        // Пропускаем heartbeat сообщения
        if (e.data.trim() === ':heartbeat' || e.data.trim().startsWith(':')) {
          return;
        }
        
        // Парсим JSON
        const data = JSON.parse(e.data);
        setEvent({ type: 'progress', data });
      } catch (error) {
        // Игнорируем ошибки парсинга для heartbeat и других служебных сообщений
        if (e.data && !e.data.includes(':heartbeat') && !e.data.trim().startsWith(':')) {
          console.error('Error parsing SSE message:', error, 'Data:', e.data);
        }
      }
    };

    // Обработка событий типа 'progress'
    eventSource.addEventListener('progress', (e: MessageEvent) => {
      try {
        if (!e.data || !e.data.trim()) {
          return;
        }
        
        const data = JSON.parse(e.data);
        setEvent({ type: 'progress', data });
      } catch (error) {
        console.error('Error parsing progress event:', error, 'Data:', e.data);
      }
    });

    // Обработка событий типа 'completed'
    eventSource.addEventListener('completed', (e: MessageEvent) => {
      try {
        if (e.data && e.data.trim()) {
          const data = JSON.parse(e.data);
          setEvent({ type: 'completed', data });
        } else {
          setEvent({ type: 'completed', data: {} });
        }
        eventSource.close();
        setIsConnected(false);
      } catch (error) {
        console.error('Error parsing completed event:', error, 'Data:', e.data);
        setEvent({ type: 'completed', data: {} });
        eventSource.close();
        setIsConnected(false);
      }
    });

    // Обработка событий типа 'error'
    eventSource.addEventListener('error', (e: MessageEvent) => {
      try {
        // Для событий типа 'error', data может быть строкой JSON
        if (e.data && typeof e.data === 'string' && e.data.trim()) {
          try {
            const data = JSON.parse(e.data);
            setEvent({ type: 'error', data });
          } catch (parseError) {
            // Если не JSON, создаем объект с ошибкой
            setEvent({ type: 'error', data: { error: e.data } });
          }
        } else {
          // Если data нет, это может быть ошибка соединения
          setEvent({ type: 'error', data: { error: 'Connection error or stream closed' } });
        }
        eventSource.close();
        setIsConnected(false);
      } catch (error) {
        console.error('Error handling error event:', error);
        setEvent({ type: 'error', data: { error: 'Unknown error occurred' } });
        eventSource.close();
        setIsConnected(false);
      }
    });

    // Обработка ошибок соединения (встроенное событие EventSource)
    eventSource.onerror = (error) => {
      console.error('EventSource connection error:', error);
      // onerror срабатывает при проблемах соединения, не при ошибках в данных
      if (eventSource.readyState === EventSource.CLOSED) {
        setEvent({ type: 'error', data: { error: 'Stream connection closed' } });
        setIsConnected(false);
      }
    };

    eventSourceRef.current = eventSource;

    return () => {
      eventSource.close();
      setIsConnected(false);
    };
  }, [requestId]);

  return { event, isConnected };
}

