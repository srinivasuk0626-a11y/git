output "cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "task_definition_arn" {
  value = aws_ecs_task_definition.service.arn
}

output "private_subnet_ids" {
  value = aws_subnet.private[*].id
}
