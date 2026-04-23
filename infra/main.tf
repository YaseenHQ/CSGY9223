# 1. AWS Provider Configuration
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1" # Ensure this matches your AWS console region
}

# 2. IAM Policy for Telemetry
resource "aws_iam_policy" "telemetry_policy" {
  name        = "ChatServiceTelemetryPolicy"
  description = "Allows the chat service to emit logs and metrics to CloudWatch"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams"
        ]
        Effect   = "Allow"
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Action   = "cloudwatch:PutMetricData"
        Effect   = "Allow"
        Resource = "*"
      }
    ]
  })
}

# 3. Create the Log Group where EMF logs will be sent
resource "aws_cloudwatch_log_group" "chat_service_logs" {
  name              = "chat-client-service-logs"
  retention_in_days = 7 
}


# 4. CloudWatch Dashboard for HW3 Deliverables
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "OSPSD-HW3-ChatService"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          metrics = [
            [ "OSPSD/HW3", "RequestLatency", "Service", "chat_client_service", { "stat": "Average", "label": "Avg Latency (ms)" } ]
          ]
          view    = "timeSeries"
          region  = "us-east-1"
          title   = "Request Latency (Requirement: Monitoring Latency)"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          metrics = [
            [ "OSPSD/HW3", "SuccessRate", "Service", "chat_client_service", { "stat": "Sum", "color": "#2ca02c" } ],
            [ "OSPSD/HW3", "FailureRate", "Service", "chat_client_service", { "stat": "Sum", "color": "#d62728" } ]
          ]
          view    = "bar"
          region  = "us-east-1"
          title   = "Success vs Failure Rate (Requirement: Health Monitoring)"
        }
      }
    ]
  })
}