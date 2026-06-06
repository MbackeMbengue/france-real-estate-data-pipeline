variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "EU"
}

variable "bucket_name" {
  description = "GCS bucket name"
  type        = string
}

variable "bigquery_dataset" {
  description = "BigQuery dataset name"
  type        = string
}