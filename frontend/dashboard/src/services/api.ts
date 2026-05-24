import axios from "axios";

import type {
  CreateTaskRequest,
  DashboardOverview,
  HistoryDetail,
  HistoryMetadata,
  HistoryTimeseries,
  TaskDetailResponse,
  TaskResponse,
  TaskWindowsResponse,
  WindowSpectraResponse
} from "../types/api";

export const api = axios.create({
  baseURL: "http://127.0.0.1:8000/api/v1",
  timeout: 10000
});

// ---------------- tasks ----------------------------------------------------

export async function createTask(body: CreateTaskRequest): Promise<TaskResponse> {
  const response = await api.post<TaskResponse>("/tasks", body);
  return response.data;
}

export async function stopTask(taskId: string): Promise<TaskDetailResponse> {
  const response = await api.post<TaskDetailResponse>(`/tasks/${taskId}/stop`);
  return response.data;
}

export async function listTasks(limit = 50): Promise<TaskDetailResponse[]> {
  const response = await api.get<TaskDetailResponse[]>("/tasks", { params: { limit } });
  return response.data;
}

export async function getTask(taskId: string): Promise<TaskDetailResponse> {
  const response = await api.get<TaskDetailResponse>(`/tasks/${taskId}`);
  return response.data;
}

export async function getTaskWindows(taskId: string): Promise<TaskWindowsResponse> {
  const response = await api.get<TaskWindowsResponse>(`/tasks/${taskId}/windows`);
  return response.data;
}

export async function getTaskSpectra(
  taskId: string,
  windowIndex: number
): Promise<WindowSpectraResponse> {
  const response = await api.get<WindowSpectraResponse>(`/tasks/${taskId}/spectra`, {
    params: { window_index: windowIndex }
  });
  return response.data;
}

// ---------------- dashboard ------------------------------------------------

export async function getDashboardOverview(): Promise<DashboardOverview> {
  const response = await api.get<DashboardOverview>("/dashboard/overview");
  return response.data;
}

// ---------------- offline history (replay mode) ----------------------------

export interface ListHistoryParams {
  label?: string;
  limit?: number;
  offset?: number;
}

export async function listHistory(params: ListHistoryParams = {}): Promise<HistoryMetadata[]> {
  const response = await api.get<HistoryMetadata[]>("/history", { params });
  return response.data;
}

export async function getHistory(sampleId: string): Promise<HistoryDetail> {
  const response = await api.get<HistoryDetail>(`/history/${sampleId}`);
  return response.data;
}

export async function getHistoryTimeseries(
  sampleId: string,
  fields?: string[]
): Promise<HistoryTimeseries> {
  const response = await api.get<HistoryTimeseries>(`/history/${sampleId}/timeseries`, {
    params: fields && fields.length ? { fields } : {},
    paramsSerializer: serializeFields
  });
  return response.data;
}

export async function uploadHistory(file: File): Promise<HistoryMetadata> {
  const form = new FormData();
  form.append("file", file);
  const response = await api.post<HistoryMetadata>("/history", form, {
    headers: { "Content-Type": "multipart/form-data" }
  });
  return response.data;
}

export async function deleteHistory(sampleId: string): Promise<void> {
  await api.delete(`/history/${sampleId}`);
}

function serializeFields(params: Record<string, unknown>): string {
  const parts: string[] = [];
  for (const [key, value] of Object.entries(params)) {
    if (Array.isArray(value)) {
      for (const item of value) {
        parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(String(item))}`);
      }
    } else if (value !== undefined && value !== null) {
      parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`);
    }
  }
  return parts.join("&");
}
