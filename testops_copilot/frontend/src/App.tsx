import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import GeneratePage from './pages/GeneratePage';
import TestPlanPage from './pages/TestPlanPage';
import ValidatePage from './pages/ValidatePage';
import OptimizePage from './pages/OptimizePage';
import TestsPage from './pages/TestsPage';
import TasksPage from './pages/TasksPage';
import IntegrationsPage from './pages/IntegrationsPage';
import './style.css';

function Navigation() {
  const location = useLocation();

  const navItems = [
    { path: '/', label: 'Генерация тестов' },
    { path: '/test-plan', label: 'Тест-планы' },
    { path: '/validate', label: 'Валидация' },
    { path: '/optimize', label: 'Оптимизация' },
    { path: '/tests', label: 'Поиск тестов' },
    { path: '/tasks', label: 'Задачи' },
    { path: '/integrations', label: 'Интеграции' },
  ];

  return (
    <nav className="nav">
      {navItems.map((item) => (
        <Link
          key={item.path}
          to={item.path}
          className={location.pathname === item.path ? 'nav-item active' : 'nav-item'}
        >
          {item.label}
        </Link>
      ))}
    </nav>
  );
}

function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <header className="header">
          <div className="header-content">
            <h1>TestOps Copilot</h1>
            <p>AI Assistant для автоматической генерации тест-кейсов</p>
          </div>
        </header>
        <Navigation />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<GeneratePage />} />
            <Route path="/test-plan" element={<TestPlanPage />} />
            <Route path="/validate" element={<ValidatePage />} />
            <Route path="/optimize" element={<OptimizePage />} />
            <Route path="/tests" element={<TestsPage />} />
            <Route path="/tasks" element={<TasksPage />} />
            <Route path="/integrations" element={<IntegrationsPage />} />
          </Routes>
        </main>
        <footer className="footer">
          <p>TestOps Copilot v1.0.0 | API: <a href="/docs" target="_blank" rel="noopener noreferrer">/docs</a></p>
        </footer>
      </div>
    </BrowserRouter>
  );
}

export default App;

