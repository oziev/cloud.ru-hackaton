export interface GenerateTestCasesRequest {
  url: string;
  requirements: string[];
  test_type: 'manual' | 'automated' | 'both';
  options?: Record<string, any>;
  use_langgraph?: boolean;
}

export interface GenerateAPITestsRequest {
  openapi_url?: string;
  openapi_spec?: string;
  endpoints?: string[];
  test_types?: string[];
  options?: Record<string, any>;
}

export interface GenerateResponse {
  request_id: string;
  task_id: string;
  status: string;
  stream_url: string;
  created_at: string;
  endpoints_count?: number;
}

export interface TaskStatus {
  request_id: string;
  status: string;
  current_step?: string;
  progress?: number;
  started_at?: string;
  completed_at?: string;
  estimated_completion?: string;
  result_summary?: {
    tests_generated?: number;
    tests_validated?: number;
    tests_optimized?: number;
    test_type?: string;
  };
  error_message?: string;
  retry_count?: number;
  tests?: TestCase[];
  metrics?: GenerationMetric[];
}

export interface TestCase {
  test_id: string;
  test_name: string;
  test_type: string;
  test_code?: string;
  priority?: number;
  allure_tags?: string[];
  validation_status?: string;
  created_at: string;
}

export interface GenerationMetric {
  agent_name: string;
  duration_ms: number;
  status: string;
  llm_tokens_total?: number;
}

export interface TestSearchResponse {
  tests: TestCase[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

export interface ValidateRequest {
  test_code: string;
  validation_level?: 'syntax' | 'semantic' | 'full';
}

export interface ValidationError {
  type: string;
  line?: number;
  message: string;
}

export interface ValidationResponse {
  valid: boolean;
  score: number;
  syntax_errors: ValidationError[];
  semantic_errors: ValidationError[];
  logic_errors: ValidationError[];
  safety_issues: any[];
  warnings: string[];
  recommendations: string[];
}

export interface OptimizeRequest {
  tests: Array<{
    test_id: string;
    test_code: string;
  }>;
  requirements: string[];
  options?: Record<string, any>;
}

export interface OptimizeResponse {
  optimized_tests: any[];
  duplicates_found: number;
  duplicates: any[];
  coverage_score: number;
  coverage_details: Record<string, any>;
  gaps: any[];
  recommendations: string[];
}

export interface GenerateTestPlanRequest {
  requirements: string[];
  project_key?: string;
  components?: string[];
  days_back?: number;
  defect_history?: any[];
  options?: Record<string, any>;
}

export interface GenerateTestPlanResponse {
  request_id: string;
  test_plan: {
    metadata: Record<string, any>;
    test_cases: any[];
    coverage: Record<string, any>;
  };
  defect_analysis?: Record<string, any>;
  created_at: string;
}

export interface PrioritizeTestsRequest {
  tests: any[];
  project_key?: string;
  components?: string[];
}

export interface PrioritizeTestsResponse {
  prioritized_tests: any[];
  defect_analysis?: Record<string, any>;
}

export interface IntegrationStatus {
  jira: {
    connected: boolean;
    message?: string;
  };
  allure: {
    connected: boolean;
    message?: string;
  };
  configuration_status: Record<string, any>;
}

