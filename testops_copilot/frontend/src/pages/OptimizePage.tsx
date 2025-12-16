import React, { useState } from 'react';
import { apiClient } from '../utils/api';
import type { OptimizeRequest, OptimizeResponse } from '../types/api';

export default function OptimizePage() {
  const [form, setForm] = useState<OptimizeRequest>({
    tests: [{ test_id: '1', test_code: '' }],
    requirements: [''],
  });
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<OptimizeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const requirements = form.requirements.filter((r) => r.trim() !== '');
      if (requirements.length === 0) {
        setError('Добавьте хотя бы одно требование');
        setLoading(false);
        return;
      }

      const tests = form.tests.filter((t) => t.test_code.trim() !== '');
      if (tests.length === 0) {
        setError('Добавьте хотя бы один тест');
        setLoading(false);
        return;
      }

      const response = await apiClient.optimize.tests({
        ...form,
        requirements,
        tests,
      });
      setResult(response);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Ошибка оптимизации');
    } finally {
      setLoading(false);
    }
  };

  const addTest = () => {
    setForm({
      ...form,
      tests: [...form.tests, { test_id: String(form.tests.length + 1), test_code: '' }],
    });
  };

  const removeTest = (index: number) => {
    const newTests = form.tests.filter((_, i) => i !== index);
    setForm({ ...form, tests: newTests.length > 0 ? newTests : [{ test_id: '1', test_code: '' }] });
  };

  const updateTest = (index: number, code: string) => {
    const newTests = [...form.tests];
    newTests[index].test_code = code;
    setForm({ ...form, tests: newTests });
  };

  const addRequirement = () => {
    setForm({ ...form, requirements: [...form.requirements, ''] });
  };

  const removeRequirement = (index: number) => {
    const newRequirements = form.requirements.filter((_, i) => i !== index);
    setForm({ ...form, requirements: newRequirements.length > 0 ? newRequirements : [''] });
  };

  return (
    <div className="page">
      <div className="page-header">
        <h2>Оптимизация тестов</h2>
        <p>Дедупликация, анализ покрытия и оптимизация тест-кейсов</p>
      </div>

      <form onSubmit={handleSubmit} className="form">
        <div className="form-group">
          <label>Тесты</label>
          {form.tests.map((test, index) => (
            <div key={index} className="test-input-group">
              <div className="test-header">
                <strong>Тест {index + 1}</strong>
                {form.tests.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeTest(index)}
                    className="btn-remove"
                  >
                    Удалить
                  </button>
                )}
              </div>
              <textarea
                rows={8}
                value={test.test_code}
                onChange={(e) => updateTest(index, e.target.value)}
                placeholder="Вставьте код теста..."
              />
            </div>
          ))}
          <button type="button" onClick={addTest} className="btn-secondary">
            Добавить тест
          </button>
        </div>

        <div className="form-group">
          <label>Требования</label>
          {form.requirements.map((req, index) => (
            <div key={index} className="input-group">
              <input
                type="text"
                value={req}
                onChange={(e) => {
                  const newRequirements = [...form.requirements];
                  newRequirements[index] = e.target.value;
                  setForm({ ...form, requirements: newRequirements });
                }}
                placeholder="Введите требование"
              />
              {form.requirements.length > 1 && (
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

        <button type="submit" className="btn-primary" disabled={loading}>
          {loading ? 'Оптимизация...' : 'Оптимизировать тесты'}
        </button>
      </form>

      {error && <div className="alert alert-error">{error}</div>}

      {result && (
        <div className="result-section">
          <h3>Результаты оптимизации</h3>

          <div className="optimization-stats">
            <div className="stat-item">
              <strong>Дубликатов найдено:</strong> {result.duplicates_found}
            </div>
            <div className="stat-item">
              <strong>Оценка покрытия:</strong> {result.coverage_score.toFixed(2)}%
            </div>
            <div className="stat-item">
              <strong>Оптимизировано тестов:</strong> {result.optimized_tests.length}
            </div>
          </div>

          {result.duplicates.length > 0 && (
            <div className="duplicates-section">
              <h4>Найденные дубликаты</h4>
              {result.duplicates.map((dup, index) => (
                <div key={index} className="duplicate-item">
                  <pre>{JSON.stringify(dup, null, 2)}</pre>
                </div>
              ))}
            </div>
          )}

          {result.optimized_tests.length > 0 && (
            <div className="optimized-tests">
              <h4>Оптимизированные тесты</h4>
              {result.optimized_tests.map((test, index) => (
                <div key={index} className="optimized-test">
                  <details>
                    <summary>Тест {index + 1}</summary>
                    <pre>{test.test_code || JSON.stringify(test, null, 2)}</pre>
                  </details>
                </div>
              ))}
            </div>
          )}

          {result.gaps.length > 0 && (
            <div className="gaps-section">
              <h4>Пробелы в покрытии</h4>
              {result.gaps.map((gap, index) => (
                <div key={index} className="gap-item">
                  <pre>{JSON.stringify(gap, null, 2)}</pre>
                </div>
              ))}
            </div>
          )}

          {result.recommendations.length > 0 && (
            <div className="recommendations-section">
              <h4>Рекомендации</h4>
              {result.recommendations.map((rec, index) => (
                <div key={index} className="recommendation-item">{rec}</div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

