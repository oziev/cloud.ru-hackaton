import { useState, useEffect } from 'react';
import { apiClient } from '../utils/api';
import type { IntegrationStatus } from '../types/api';

export default function IntegrationsPage() {
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<IntegrationStatus | null>(null);
  const [configStatus, setConfigStatus] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadStatus();
    loadConfigStatus();
  }, []);

  const loadStatus = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.integrations.testConnection('all');
      setStatus(response);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Ошибка проверки подключений');
    } finally {
      setLoading(false);
    }
  };

  const loadConfigStatus = async () => {
    try {
      const response = await apiClient.integrations.getConfigurationStatus();
      setConfigStatus(response);
    } catch (err: any) {
      console.error('Error loading config status:', err);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <h2>Интеграции</h2>
        <p>Настройка и проверка подключений к внешним системам</p>
      </div>

      <div className="actions-bar">
        <button onClick={loadStatus} className="btn-primary" disabled={loading}>
          {loading ? 'Проверка...' : 'Проверить подключения'}
        </button>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {status && (
        <div className="integrations-status">
          <div className="integration-card">
            <h3>Jira</h3>
            <div className={`status-indicator ${status.jira.connected ? 'connected' : 'disconnected'}`}>
              {status.jira.connected ? 'Подключено' : 'Не подключено'}
            </div>
            {status.jira.message && (
              <div className="status-message">{status.jira.message}</div>
            )}
          </div>

          <div className="integration-card">
            <h3>Allure TestOps</h3>
            <div className={`status-indicator ${status.allure.connected ? 'connected' : 'disconnected'}`}>
              {status.allure.connected ? 'Подключено' : 'Не подключено'}
            </div>
            {status.allure.message && (
              <div className="status-message">{status.allure.message}</div>
            )}
          </div>
        </div>
      )}

      {configStatus && (
        <div className="config-section">
          <h3>Статус конфигурации</h3>
          <div className="config-details">
            <div className="config-item">
              <strong>Статус:</strong> {configStatus.status}
            </div>
            <div className="config-item">
              <strong>Конфигурация:</strong>
              <pre>{JSON.stringify(configStatus.configuration, null, 2)}</pre>
            </div>
            {configStatus.instructions && (
              <div className="config-item">
                <strong>Инструкции:</strong>
                <pre>{JSON.stringify(configStatus.instructions, null, 2)}</pre>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

