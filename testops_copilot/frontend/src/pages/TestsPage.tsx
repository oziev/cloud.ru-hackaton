import { useState, useEffect } from 'react';
import { apiClient } from '../utils/api';
import type { TestSearchResponse, TestCase } from '../types/api';

export default function TestsPage() {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [testType, setTestType] = useState('');
  const [priority, setPriority] = useState<number | undefined>();
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(20);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<TestSearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [exportLoading, setExportLoading] = useState(false);

  useEffect(() => {
    loadTests();
  }, [search, statusFilter, testType, priority, page, perPage]);

  const loadTests = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.tests.search(
        search || undefined,
        statusFilter || undefined,
        testType || undefined,
        undefined,
        priority,
        page,
        perPage
      );
      setData(response);
    } catch (err: any) {
      const errorMsg = err.code === 'ERR_NETWORK' || err.message?.includes('Network Error') || err.message?.includes('Connection reset')
        ? 'Не удалось подключиться к серверу. Проверьте, что API Gateway запущен на порту 8000.'
        : err.response?.data?.detail || err.message || 'Ошибка загрузки тестов';
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async (format: 'zip' | 'json' | 'yaml') => {
    setExportLoading(true);
    try {
      const blob = await apiClient.tests.export(undefined, format, true);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `tests_export_${new Date().toISOString().slice(0, 10)}.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      const errorMsg = err.code === 'ERR_NETWORK' || err.message?.includes('Network Error')
        ? 'Не удалось подключиться к серверу. Проверьте, что API Gateway запущен.'
        : err.response?.data?.detail || err.message || 'Ошибка экспорта';
      setError(errorMsg);
    } finally {
      setExportLoading(false);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <h2>Поиск и экспорт тестов</h2>
        <p>Поиск, фильтрация и экспорт сгенерированных тест-кейсов</p>
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

      <div className="filters-section">
        <div className="filters-grid">
          <div className="form-group">
            <label htmlFor="search">Поиск</label>
            <input
              id="search"
              type="text"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              placeholder="Поиск по названию или коду..."
            />
          </div>

          <div className="form-group">
            <label htmlFor="status_filter">Статус валидации</label>
            <select
              id="status_filter"
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
            >
              <option value="">Все</option>
              <option value="passed">Passed</option>
              <option value="warning">Warning</option>
              <option value="failed">Failed</option>
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="test_type">Тип теста</label>
            <select
              id="test_type"
              value={testType}
              onChange={(e) => {
                setTestType(e.target.value);
                setPage(1);
              }}
            >
              <option value="">Все</option>
              <option value="automated">Автоматизированные</option>
              <option value="manual">Ручные</option>
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="priority">Приоритет</label>
            <input
              id="priority"
              type="number"
              value={priority || ''}
              onChange={(e) => {
                const val = e.target.value ? parseInt(e.target.value) : undefined;
                setPriority(val);
                setPage(1);
              }}
              placeholder="Приоритет"
              min="1"
              max="5"
            />
          </div>

          <div className="form-group">
            <label htmlFor="per_page">На странице</label>
            <select
              id="per_page"
              value={perPage}
              onChange={(e) => {
                setPerPage(parseInt(e.target.value));
                setPage(1);
              }}
            >
              <option value="10">10</option>
              <option value="20">20</option>
              <option value="50">50</option>
              <option value="100">100</option>
            </select>
          </div>
        </div>

        <div className="export-buttons">
          <button
            onClick={() => handleExport('zip')}
            className="btn-secondary"
            disabled={exportLoading}
          >
            {exportLoading ? 'Экспорт...' : 'Экспорт ZIP'}
          </button>
          <button
            onClick={() => handleExport('json')}
            className="btn-secondary"
            disabled={exportLoading}
          >
            Экспорт JSON
          </button>
          <button
            onClick={() => handleExport('yaml')}
            className="btn-secondary"
            disabled={exportLoading}
          >
            Экспорт YAML
          </button>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {loading ? (
        <div className="loading">Загрузка...</div>
      ) : data ? (
        <>
          <div className="results-info">
            Найдено тестов: {data.total} | Страница {data.page} из {data.total_pages}
          </div>

          <div className="tests-table">
            <table>
              <thead>
                <tr>
                  <th>Название</th>
                  <th>Тип</th>
                  <th>Приоритет</th>
                  <th>Статус</th>
                  <th>Дата создания</th>
                  <th>Действия</th>
                </tr>
              </thead>
              <tbody>
                {data.tests.map((test) => (
                  <TestRow key={test.test_id} test={test} />
                ))}
              </tbody>
            </table>
          </div>

          {data.total_pages > 1 && (
            <div className="pagination">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="btn-secondary"
              >
                Назад
              </button>
              <span>
                Страница {data.page} из {data.total_pages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
                disabled={page === data.total_pages}
                className="btn-secondary"
              >
                Вперед
              </button>
            </div>
          )}
        </>
      ) : null}
    </div>
  );
}

function TestRow({ test }: { test: TestCase }) {
  const [showCode, setShowCode] = useState(false);

  return (
    <>
      <tr>
        <td>{test.test_name}</td>
        <td>
          <span className={`test-type-badge ${test.test_type}`}>
            {test.test_type === 'automated' ? 'Авто' : 'Ручной'}
          </span>
        </td>
        <td>{test.priority || '-'}</td>
        <td>
          <span className={`status-badge status-${test.validation_status || 'unknown'}`}>
            {test.validation_status || 'Неизвестно'}
          </span>
        </td>
        <td>{new Date(test.created_at).toLocaleString('ru')}</td>
        <td>
          {test.test_code && (
            <button onClick={() => setShowCode(!showCode)} className="btn-link">
              {showCode ? 'Скрыть код' : 'Показать код'}
            </button>
          )}
        </td>
      </tr>
      {showCode && test.test_code && (
        <tr>
          <td colSpan={6}>
            <pre className="test-code-preview">{test.test_code}</pre>
          </td>
        </tr>
      )}
    </>
  );
}

