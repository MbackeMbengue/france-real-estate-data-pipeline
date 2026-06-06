output "bucket_name" {
  value = google_storage_bucket.data_lake.name
}

output "bigquery_dataset" {
  value = google_bigquery_dataset.analytics.dataset_id
}