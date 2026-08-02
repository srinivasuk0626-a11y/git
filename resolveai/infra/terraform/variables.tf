variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Resource name prefix"
  type        = string
  default     = "resolveai"
}

variable "container_image" {
  description = "Published ResolveAI container image"
  type        = string
}

variable "elastic_url_secret_arn" {
  description = "Secrets Manager ARN containing ELASTICSEARCH_URL"
  type        = string
}
