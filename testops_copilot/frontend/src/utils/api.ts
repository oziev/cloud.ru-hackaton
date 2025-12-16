import axios from 'axios';
import type {
  GenerateTestCasesRequest,
  GenerateAPITestsRequest,
  GenerateResponse,
  TaskStatus,
  TestSearchResponse,
  ValidateRequest,
  ValidationResponse,
  OptimizeRequest,
  OptimizeResponse,
  GenerateTestPlanRequest,
  GenerateTestPlanResponse,
  PrioritizeTestsRequest,
  PrioritizeTestsResponse,
  IntegrationStatus
} from '../types/api';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const apiClient = {
  generate: {
    testCases: async (data: GenerateTestCasesRequest): Promise<GenerateResponse> => {
      const response = await api.post<GenerateResponse>('/generate/test-cases', data);
      return response.data;
    },
    apiTests: async (data: GenerateAPITestsRequest): Promise<GenerateResponse> => {
      const response = await api.post<GenerateResponse>('/generate/api-tests', data);
      return response.data;
    },
  },

  tasks: {
    list: async (limit = 20, offset = 0, status?: string): Promise<TaskStatus[]> => {
      const response = await api.get<TaskStatus[]>('/tasks', {
        params: { limit, offset, ...(status && { status }) },
      });
      return response.data;
    },
    get: async (taskId: string, includeTests = false, includeMetrics = false): Promise<TaskStatus> => {
      const response = await api.get<TaskStatus>(`/tasks/${taskId}`, {
        params: { include_tests: includeTests, include_metrics: includeMetrics },
      });
      return response.data;
    },
    resume: async (taskId: string): Promise<void> => {
      await api.post(`/tasks/${taskId}/resume`);
    },
  },

  tests: {
    search: async (
      search?: string,
      statusFilter?: string,
      testType?: string,
      requestId?: string,
      priority?: number,
      page = 1,
      perPage = 20
    ): Promise<TestSearchResponse> => {
      const response = await api.get<TestSearchResponse>('/tests', {
        params: {
          search,
          status_filter: statusFilter,
          test_type: testType,
          request_id: requestId,
          priority,
          page,
          per_page: perPage,
        },
      });
      return response.data;
    },
    export: async (requestId?: string, format = 'zip', includeCode = true): Promise<Blob> => {
      const response = await api.get('/tests/export', {
        params: { request_id: requestId, format, include_code: includeCode },
        responseType: 'blob',
      });
      return response.data;
    },
  },

  validate: {
    test: async (data: ValidateRequest): Promise<ValidationResponse> => {
      const response = await api.post<ValidationResponse>('/validate/tests', data);
      return response.data;
    },
  },

  optimize: {
    tests: async (data: OptimizeRequest): Promise<OptimizeResponse> => {
      const response = await api.post<OptimizeResponse>('/optimize/tests', data);
      return response.data;
    },
  },

  testPlan: {
    generate: async (data: GenerateTestPlanRequest): Promise<GenerateTestPlanResponse> => {
      const response = await api.post<GenerateTestPlanResponse>('/test-plan/generate', data);
      return response.data;
    },
    prioritize: async (data: PrioritizeTestsRequest): Promise<PrioritizeTestsResponse> => {
      const response = await api.post<PrioritizeTestsResponse>('/test-plan/prioritize', data);
      return response.data;
    },
  },

  integrations: {
    testConnection: async (source = 'all'): Promise<IntegrationStatus> => {
      const response = await api.get<IntegrationStatus>('/integrations/test-connection', {
        params: { source },
      });
      return response.data;
    },
    getConfigurationStatus: async (): Promise<any> => {
      const response = await api.get('/integrations/configuration-status');
      return response.data;
    },
  },

  stream: {
    getUrl: (requestId: string): string => {
      return `${API_BASE_URL}/stream/${requestId}`;
    },
  },
};

export default apiClient;

