from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import RouteRequestSerializer
from .services.geocoding import LocationError
from .services.http import ExternalServiceError
from .services.optimizer import NoFeasiblePlan
from .services.planner import plan_trip


class RoutePlanView(APIView):
    """Plan a route between two US locations with cost-optimal fuel stops.

    POST {"start": "Chicago, IL", "finish": "Los Angeles, CA"}
    """

    def post(self, request):
        serializer = RouteRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        v = serializer.validated_data
        try:
            plan = plan_trip(v["start"], v["finish"])
        except LocationError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except NoFeasiblePlan as exc:
            return Response({"error": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except ExternalServiceError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(plan)
