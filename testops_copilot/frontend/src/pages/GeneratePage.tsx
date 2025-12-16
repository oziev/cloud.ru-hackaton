import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../utils/api';
import type { GenerateTestCasesRequest, GenerateAPITestsRequest } from '../types/api';

export default function GeneratePage() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<'ui' | 'api'>('ui');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [uiForm, setUiForm] = useState<GenerateTestCasesRequest>({
    url: '',
    requirements: [''],
    test_type: 'both',
    use_langgraph: true,
  });

  const [apiForm, setApiForm] = useState<GenerateAPITestsRequest>({
    openapi_url: '',
    endpoints: [],
    test_types: ['positive'],
  });

  const handleUiSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const requirements = uiForm.requirements.filter((r) => r.trim() !== '');
      if (requirements.length === 0) {
        setError('Добавьте хотя бы одно требование');
        setLoading(false);
        return;
      }

      await apiClient.generate.testCases({
        ...uiForm,
        requirements,
      });

      // Переходим на страницу задач БЕЗ автоматического выбора задачи
      navigate('/tasks');
    } catch (err: any) {
      const errorMsg = err.code === 'ERR_NETWORK' || err.message?.includes('Network Error')
        ? 'Не удалось подключиться к серверу. Проверьте, что API Gateway запущен.'
        : err.response?.data?.detail || err.message || 'Ошибка генерации UI тестов';
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const handleApiSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      if (!apiForm.openapi_url && !apiForm.openapi_spec) {
        setError('Укажите URL OpenAPI спецификации или загрузите файл');
        setLoading(false);
        return;
      }

      // Подготавливаем данные для отправки
      const requestData: GenerateAPITestsRequest = {
        openapi_url: apiForm.openapi_url || undefined,
        openapi_spec: apiForm.openapi_spec || undefined,
        endpoints: apiForm.endpoints && apiForm.endpoints.length > 0 ? apiForm.endpoints : undefined,
        test_types: apiForm.test_types && apiForm.test_types.length > 0 ? apiForm.test_types : ['positive'],
        options: apiForm.options
      };

      await apiClient.generate.apiTests(requestData);
      // Переходим на страницу задач БЕЗ автоматического выбора задачи
      navigate('/tasks');
    } catch (err: any) {
      const errorMsg = err.code === 'ERR_NETWORK' || err.message?.includes('Network Error')
        ? 'Не удалось подключиться к серверу. Проверьте, что API Gateway запущен.'
        : err.response?.data?.detail || err.message || 'Ошибка генерации API тестов';
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const addRequirement = () => {
    setUiForm({ ...uiForm, requirements: [...uiForm.requirements, ''] });
  };

  const removeRequirement = (index: number) => {
    const newRequirements = uiForm.requirements.filter((_, i) => i !== index);
    setUiForm({ ...uiForm, requirements: newRequirements.length > 0 ? newRequirements : [''] });
  };

  const updateRequirement = (index: number, value: string) => {
    const newRequirements = [...uiForm.requirements];
    newRequirements[index] = value;
    setUiForm({ ...uiForm, requirements: newRequirements });
  };

  return (
    <div className="page">
      <div className="page-header">
        <h2>Генерация тест-кейсов</h2>
        <p>Автоматическая генерация UI и API тестов на основе требований</p>
      </div>

      <div className="tabs">
        <button
          className={activeTab === 'ui' ? 'tab-button active' : 'tab-button'}
          onClick={() => setActiveTab('ui')}
        >
          UI Тесты
        </button>
        <button
          className={activeTab === 'api' ? 'tab-button active' : 'tab-button'}
          onClick={() => setActiveTab('api')}
        >
          API Тесты
        </button>
      </div>

      {error && (
        <div className="alert alert-error">
          {error}
        </div>
      )}

      {activeTab === 'ui' && (
        <form onSubmit={handleUiSubmit} className="form">
          <div className="form-group">
            <label htmlFor="url">URL для тестирования</label>
            <input
              id="url"
              type="url"
              value={uiForm.url}
              onChange={(e) => setUiForm({ ...uiForm, url: e.target.value })}
              placeholder="https://example.com"
              required
            />
          </div>

          <div className="form-group">
            <label>Требования</label>
            {uiForm.requirements.map((req, index) => (
              <div key={index} className="input-group">
                <input
                  type="text"
                  value={req}
                  onChange={(e) => updateRequirement(index, e.target.value)}
                  placeholder="Введите требование"
                />
                {uiForm.requirements.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeRequirement(index)}
                    className="btn-remove"
                  >
                    Удалить
                  </button>
                )}
              </div>
            ))}
            <button type="button" onClick={addRequirement} className="btn-secondary">
              Добавить требование
            </button>
          </div>

          <div className="form-group">
            <label htmlFor="test_type">Тип тестов</label>
            <select
              id="test_type"
              value={uiForm.test_type}
              onChange={(e) => setUiForm({ ...uiForm, test_type: e.target.value as any })}
            >
              <option value="both">Ручные и автоматизированные</option>
              <option value="automated">Только автоматизированные</option>
              <option value="manual">Только ручные</option>
            </select>
          </div>

          <div className="form-group">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={uiForm.use_langgraph}
                onChange={(e) => setUiForm({ ...uiForm, use_langgraph: e.target.checked })}
              />
              Использовать LangGraph workflow
            </label>
          </div>

          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? 'Генерация...' : 'Сгенерировать тесты'}
          </button>
        </form>
      )}

      {activeTab === 'api' && (
        <form onSubmit={handleApiSubmit} className="form">
          <div className="form-group">
            <label htmlFor="openapi_url">URL OpenAPI спецификации</label>
            <input
              id="openapi_url"
              type="url"
              value={apiForm.openapi_url || ''}
              onChange={(e) => setApiForm({ ...apiForm, openapi_url: e.target.value })}
              placeholder="https://petstore.swagger.io/v2/swagger.json"
            />
            <small style={{ display: 'block', marginTop: '0.5rem', color: '#666' }}>
              Пример: https://petstore.swagger.io/v2/swagger.json
            </small>
          </div>

          <div className="form-group">
            <label htmlFor="endpoints">Endpoints (через запятую, опционально)</label>
            <input
              id="endpoints"
              type="text"
              value={apiForm.endpoints?.join(', ') || ''}
              onChange={(e) => {
                const value = e.target.value;
                const endpoints = value
                  ? value.split(',').map((s) => s.trim()).filter(Boolean)
                  : [];
                setApiForm({
                  ...apiForm,
                  endpoints: endpoints.length > 0 ? endpoints : undefined,
                });
              }}
              placeholder="/pet, /store/order, /user"
            />
          </div>

          <div className="form-group">
            <label htmlFor="test_types">Типы тестов</label>
            <select
              id="test_types"
              multiple
              value={apiForm.test_types || ['positive']}
              onChange={(e) => {
                const selected = Array.from(e.target.selectedOptions, (option) => option.value);
                setApiForm({
                  ...apiForm,
                  test_types: selected.length > 0 ? selected : ['positive'],
                });
              }}
            >
              <option value="positive">Positive</option>
              <option value="negative">Negative</option>
              <option value="edge">Edge Cases</option>
            </select>
            <small>Удерживайте Ctrl для выбора нескольких (по умолчанию: Positive)</small>
          </div>

          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? 'Генерация...' : 'Сгенерировать API тесты'}
          </button>
        </form>
      )}
    </div>
  );
}

