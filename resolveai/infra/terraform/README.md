# Terraform infrastructure

This module demonstrates the security and lifecycle decisions expected for an enterprise agent:

- Private subnets
- No public IPs on application tasks
- Restricted service egress
- ECS Fargate with two replicas
- CloudWatch logs and container insights
- Secrets Manager references instead of plaintext credentials
- Health checks and immutable container deployment

A production deployment still requires an internal ALB/API Gateway path, NAT or VPC endpoints for required outbound services, a persistent checkpoint store, WAF/rate limiting, and organization-specific IAM boundaries. Those are intentionally left environment-dependent instead of being fabricated.
