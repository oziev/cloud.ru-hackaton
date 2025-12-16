import React, { useState } from 'react';
import { apiClient } from '../utils/api';
import type { GenerateTestPlanRequest, PrioritizeTestsRequest } from '../types/api';

export default function TestPlanPage() {
  const [activeTab, setActiveTab] = useState<'generate' | 'prioritize'>('generate');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<any>(null);

  const [generateForm, setGenerateForm] = useState<GenerateTestPlanRequest>({
    requirements: [''],
    days_back: 90,
  });

  const [prioritizeForm, setPrioritizeForm] = useState<PrioritizeTestsRequest>({
    tests: [],
  });

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const requirements = generateForm.requirements.filter((r) => r.trim() !== '');
      if (requirements.length === 0) {
        setError('Добавьте хотя бы одно требование');
        setLoading(false);
        return;
      }

      const response = await apiClient.testPlan.generate({
        ...generateForm,
        requirements,
      });
      setResult(response);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Ошибка генерации тест-плана');
    } finally {
      setLoading(false);
    }
  };

  const handlePrioritize = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      if (prioritizeForm.tests.length === 0) {
        setError('Добавьте тесты для приоритизации');
        setLoading(false);
        return;
      }

      const response = await apiClient.testPlan.prioritize(prioritizeForm);
      setResult(response);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Ошибка приоритизации');
    } finally {
      setLoading(false);
    }
  };

  const addRequirement = () => {
    setGenerateForm({ ...generateForm, requirements: [...generateForm.requirements, ''] });
  };

  const removeRequirement = (index: number) => {
    const newRequirements = generateForm.requirements.filter((_, i) => i !== index);
    setGenerateForm({ ...generateForm, requirements: newRequirements.length > 0 ? newRequirements : [''] });
  };

  return (
    <div className="page">
      <div className="page-header">
        <h2>Тест-планы</h2>
        <p>Генерация тест-планов и приоритизация тестов на основе анализа дефектов</p>
      </div>

      <div className="tabs">
        <button
          className={activeTab === 'generate' ? 'tab-button active' : 'tab-button'}
          onClick={() => setActiveTab('generate')}
        >
          Генерация тест-плана
        </button>
        <button
          className={activeTab === 'prioritize' ? 'tab-button active' : 'tab-button'}
          onClick={() => setActiveTab('prioritize')}
        >
          Приоритизация тестов
        </button>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {activeTab === 'generate' && (
        <form onSubmit={handleGenerate} className="form">
          <div className="form-group">
            <label>Требования</label>
            {generateForm.requirements.map((req, index) => (
              <div key={index} className="input-group">
                <input
                  type="text"
                  value={req}
                  onChange={(e) => {
                    const newRequirements = [...generateForm.requirements];
                    newRequirements[index] = e.target.value;
                    setGenerateForm({ ...generateForm, requirements: newRequirements });
                  }}
                  placeholder="Введите требование"
                />
                {generateForm.requirements.length > 1 && (
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
            <label htmlFor="project_key">Ключ проекта (опционально)</label>
            <input
              id="project_key"
              type="text"
              value={generateForm.project_key || ''}
              onChange={(e) => setGenerateForm({ ...generateForm, project_key: e.target.value })}
              placeholder="PROJECT-KEY"
            />
          </div>

          <div className="form-group">
            <label htmlFor="days_back">Дней назад для анализа дефектов</label>
            <input
              id="days_back"
              type="number"
              value={generateForm.days_back}
              onChange={(e) => setGenerateForm({ ...generateForm, days_back: parseInt(e.target.value) })}
              min="1"
              max="365"
            />
          </div>

          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? 'Генерация...' : 'Сгенерировать тест-план'}
          </button>
        </form>
      )}

      {activeTab === 'prioritize' && (
        <form onSubmit={handlePrioritize} className="form">
          <div className="form-group">
            <label>Тесты (JSON массив)</label>
            <textarea
              rows={10}
              value={JSON.stringify(prioritizeForm.tests, null, 2)}
              onChange={(e) => {
                try {
                  const tests = JSON.parse(e.target.value);
                  setPrioritizeForm({ ...prioritizeForm, tests });
                } catch {
                  // Invalid JSON
                }
              }}
              placeholder='[{"test_id": "1", "test_name": "Test 1", ...}]'
            />
          </div>

          <div className="form-group">
            <label htmlFor="prioritize_project_key">Ключ проекта (опционально)</label>
            <input
              id="prioritize_project_key"
              type="text"
              value={prioritizeForm.project_key || ''}
              onChange={(e) => setPrioritizeForm({ ...prioritizeForm, project_key: e.target.value })}
              placeholder="PROJECT-KEY"
            />
          </div>

          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? 'Приоритизация...' : 'Приоритизировать тесты'}
          </button>
        </form>
      )}

      {result && (
        <div className="result-section">
          <h3>Результат</h3>
          <pre className="result-json">{JSON.stringify(result, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}

