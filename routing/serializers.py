from rest_framework import serializers


class RouteRequestSerializer(serializers.Serializer):
    start = serializers.CharField(max_length=300, help_text='"City, ST", "lat,lon" or a US address')
    finish = serializers.CharField(max_length=300, help_text='"City, ST", "lat,lon" or a US address')

    def validate(self, attrs):
        if attrs["start"].strip().lower() == attrs["finish"].strip().lower():
            raise serializers.ValidationError("start and finish must be different locations.")
        return attrs
