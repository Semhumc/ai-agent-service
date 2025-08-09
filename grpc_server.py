import grpc
from concurrent import futures
from ai_agents import ai_agent

import json
import logging

import grpc_server_pb2 as grpc_server_pb2
import grpc_server_pb2_grpc as grpc_server_pb2_grpc

class AIService(grpc_server_pb2_grpc.AIServiceServicer):
    def __init__(self):
        self.agent = ai_agent()

    def GenerateTripPlan(self, request: ai_service_pb2.PromptRequest, context):
        try:
            prompt_data = json.loads(request.prompt_data)
            trip_plan = self.agent.generate_trip_plan(prompt_data)
            return grpc_server_pb2.TripPlanResponse(trip_plan=trip_plan)
        except Exception as e:
            logging.error(f"Error generating trip plan: {str(e)}")
            context.set_details(f"Error: {str(e)}")
            context.set_code(grpc.StatusCode.INTERNAL)
            return grpc_server_pb2.TripPlanResponse(trip_plan="")