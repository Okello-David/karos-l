from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .serializers import LoginSerializer, UserSerializer


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    serializer = LoginSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    user = serializer.validated_data["user"]
    token, created = Token.objects.get_or_create(user=user)
    user_serializer = UserSerializer(user)
    return Response(
        {"token": token.key, "user": user_serializer.data},
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
def logout_view(request):
    request.auth.delete()
    return Response({"detail": "Successfully logged out."}, status=status.HTTP_200_OK)


@api_view(["GET"])
def me_view(request):
    serializer = UserSerializer(request.user)
    return Response(serializer.data)
