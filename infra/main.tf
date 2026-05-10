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
            [ { "expression": "SEARCH('{OSPSD/HW3, Service, Endpoint} MetricName=\"RequestLatency\" Service=\"chat_client_service\"', 'Average', 60)", "label": "$${LABEL} [avg: $${AVG}]", "id": "q1", "region": "us-east-1" } ]
          ]
          period  = 60
          region  = "us-east-1"
          title   = "Request Latency (Monitoring Latency)"
          view    = "timeSeries"
          yAxis = {
            left = {
              label     = "Count"
              showUnits = false
            }
          }
          stat = "Average"
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
            [ { "expression": "SEARCH('{OSPSD/HW3, Service, Endpoint} MetricName=\"SuccessRate\" Service=\"chat_client_service\"', 'Sum', 60)", "label": "Successes", "id": "q1", "region": "us-east-1" } ],
            [ { "expression": "SEARCH('{OSPSD/HW3, Service, Endpoint} MetricName=\"FailureRate\" Service=\"chat_client_service\"', 'Sum', 60)", "label": "Failures", "id": "q2", "region": "us-east-1" } ]
          ]
          view    = "timeSeries"
          stacked = false
          region  = "us-east-1"
          title   = "Service Health: Success vs Failure Rate (Health Monitoring)"
          yAxis = {
            left = {
              label     = "Count"
              showUnits = false
            }
          }
          stat   = "Average"
          period = 300
        }
      }
    ]
  })
}