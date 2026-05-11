export interface SampleMetadata {
  sample_id: string;
  label: string | null;
  captured_at: string | null;
  source_name: string | null;
  has_vision: boolean;
  has_sensor: boolean;
  file_path: string;
  window_count: number;
  ingested_at: string;
}

export type WindowRow = Record<string, string | number | boolean | null>;

export interface SampleDetail {
  metadata: SampleMetadata;
  rows: WindowRow[];
}

export interface SampleTimeseries {
  sample_id: string;
  fields: string[];
  points: WindowRow[];
}

export interface IngestErrorBody {
  detail: {
    message: string;
    missing_columns: string[];
  };
}
