import React, { useState } from 'react';
import { apiClient } from '../utils/api';
import type { ValidateRequest, ValidationResponse } from '../types/api';

export default function ValidatePage() {
  const [form, setForm] = useState<ValidateRequest>({
    test_code: '',
    validation_level: 'full',
  });
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ValidationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await apiClient.validate.test(form);
      setResult(response);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Ошибка валидации');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <h2>Валидация тестов</h2>
        <p>Проверка качества и корректности тест-кейсов</p>
      </div>

      <form onSubmit={handleSubmit} className="form">
        <div className="form-group">
          <label htmlFor="validation_level">Уровень валидации</label>
          <select
            id="validation_level"
            value={form.validation_level}
            onChange={(e) => setForm({ ...form, validation_level: e.target.value as any })}
          >
            <option value="syntax">Синтаксис</option>
            <option value="semantic">Семантика</option>
            <option value="full">Полная валидация</option>
          </select>
        </div>

        <div className="form-group">
          <label htmlFor="test_code">Код теста</label>
          <textarea
            id="test_code"
            rows={15}
            value={form.test_code}
            onChange={(e) => setForm({ ...form, test_code: e.target.value })}
            placeholder="Вставьте код теста для валидации..."
            required
          />
        </div>

        <button type="submit" className="btn-primary" disabled={loading}>
          {loading ? 'Валидация...' : 'Валидировать тест'}
        </button>
      </form>

      {error && <div className="alert alert-error">{error}</div>}

      {result && (
        <div className="result-section">
          <div className={`validation-result ${result.valid ? 'valid' : 'invalid'}`}>
            <h3>
              {result.valid ? 'Тест валиден' : 'Тест содержит ошибки'}
            </h3>
            <div className="validation-score">
              <strong>Оценка качества:</strong> {result.score}/100
            </div>
          </div>

          {result.syntax_errors.length > 0 && (
            <div className="validation-errors">
              <h4>Синтаксические ошибки</h4>
              {result.syntax_errors.map((err, index) => (
                <div key={index} className="error-item">
                  <strong>Строка {err.line}:</strong> {err.message}
                </div>
              ))}
            </div>
          )}

          {result.semantic_errors.length > 0 && (
            <div className="validation-errors">
              <h4>Семантические ошибки</h4>
              {result.semantic_errors.map((err, index) => (
                <div key={index} className="error-item">
                  <strong>Строка {err.line}:</strong> {err.message}
                </div>
              ))}
            </div>
          )}

          {result.logic_errors.length > 0 && (
            <div className="validation-errors">
              <h4>Логические ошибки</h4>
              {result.logic_errors.map((err, index) => (
                <div key={index} className="error-item">
                  <strong>Строка {err.line}:</strong> {err.message}
                </div>
              ))}
            </div>
          )}

          {result.safety_issues.length > 0 && (
            <div className="validation-warnings">
              <h4>Проблемы безопасности</h4>
              {result.safety_issues.map((issue, index) => (
                <div key={index} className="warning-item">
                  {JSON.stringify(issue, null, 2)}
                </div>
              ))}
            </div>
          )}

          {result.warnings.length > 0 && (
            <div className="validation-warnings">
              <h4>Предупреждения</h4>
              {result.warnings.map((warning, index) => (
                <div key={index} className="warning-item">{warning}</div>
              ))}
            </div>
          )}

          {result.recommendations.length > 0 && (
            <div className="validation-recommendations">
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

