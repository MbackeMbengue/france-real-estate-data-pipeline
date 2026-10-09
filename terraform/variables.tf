variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "gcp_region" {
  description = "Région GCP par défaut du provider (ressources régionales)"
  type        = string
  default     = "europe-west1"
}

variable "region" {
  description = "Localisation du bucket GCS et du dataset BigQuery (multi-région EU)"
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