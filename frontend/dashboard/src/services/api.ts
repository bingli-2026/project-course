import axios from "axios";

import type {
  SampleDetail,
  SampleMetadata,
  SampleTimeseries
} from "../types/sample";

export const api = axios.create({
  baseURL: "http://127.0.0.1:8000/api/v1",
  timeout: 10000
});

export interface ListSamplesParams {
  label?: string;
  limit?: number;
  offset?: number;
}

export async function listSamples(
  params: ListSamplesParams = {}
): Promise<SampleMetadata[]> {
  const response = await api.get<SampleMetadata[]>("/samples", { params });
  return response.data;
}

export async function getSample(sampleId: string): Promise<SampleDetail> {
  const response = await api.get<SampleDetail>(`/samples/${sampleId}`);
  return response.data;
}

export async function getTimeseries(
  sampleId: string,
  fields?: string[]
): Promise<SampleTimeseries> {
  const response = await api.get<SampleTimeseries>(
    `/samples/${sampleId}/timeseries`,
    { params: fields && fields.length ? { fields } : {}, paramsSerializer: serializeFields }
  );
  return response.data;
}

export async function uploadSample(file: File): Promise<SampleMetadata> {
  const form = new FormData();
  form.append("file", file);
  const response = await api.post<SampleMetadata>("/samples", form, {
    headers: { "Content-Type": "multipart/form-data" }
  });
  return response.data;
}

export async function deleteSample(sampleId: string): Promise<void> {
  await api.delete(`/samples/${sampleId}`);
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
