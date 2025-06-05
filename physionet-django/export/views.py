import os

from django.shortcuts import get_object_or_404
from django.http import FileResponse
from export.serializers import PublishedProjectSerializer, PublishedProjectDetailSerializer, ProjectVersionsSerializer
from rest_framework import generics, permissions
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from rest_framework import mixins
from rest_framework.response import Response
from rest_framework.views import APIView
from search.views import get_content
from project.models import ProjectType

from project.models import PublishedProject
from project.authorization.access import can_access_project

# Temporary imports for Database List Function.
from django.http import JsonResponse


def database_list(request):
    """
    List all published databases
    """
    projects = PublishedProject.objects.filter(resource_type=0).order_by(
        'publish_datetime')
    serializer = PublishedProjectSerializer(projects, many=True)
    return JsonResponse(serializer.data, safe=False)


class PublishedProjectList(mixins.ListModelMixin, generics.GenericAPIView):
    """
    List all Published Projects
    """
    queryset = PublishedProject.objects.all().order_by('id')
    authentication_classes = [SessionAuthentication, BasicAuthentication]
    serializer_class = PublishedProjectSerializer

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class ProjectVersionList(mixins.ListModelMixin, generics.GenericAPIView):
    """
    List all versions of a specific project
    """
    serializer_class = ProjectVersionsSerializer

    def get_queryset(self):
        project_slug = self.kwargs.get('project_slug')
        queryset = PublishedProject.objects.filter(slug=project_slug).order_by('id')
        return queryset

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class PublishedProjectDetail(mixins.RetrieveModelMixin, generics.GenericAPIView):
    """
    Retrieve an Published Project
    """
    authentication_classes = [SessionAuthentication, BasicAuthentication]

    def get(self, request, project_slug, version, *args, **kwargs):
        project = get_object_or_404(PublishedProject, slug=project_slug, version=version)
        serializer = PublishedProjectDetailSerializer(project)
        return Response(serializer.data)


class PublishedProjectSearch(mixins.ListModelMixin, generics.GenericAPIView):
    """
    Search for a Published Project using the get_content function inside Search Module's views.py
    """
    serializer_class = PublishedProjectSerializer

    def check_resource_type(self, resource_type):
        """
        Check if the resource_type requested is valid. Returns True if valid, else False
        """
        available_resource_types = ProjectType.objects.all().values_list('name', flat=True)
        for r_type in resource_type:
            if r_type != 'all' and r_type.capitalize() not in available_resource_types:
                return False
        return True

    def get_queryset(self):
        """
        Modifying the get_queryset method to return the queryset based on the search_term and resource_type
        """
        resource_type = self.request.GET.getlist('resource_type', ['all'])
        search_term = self.request.GET.get('search_term', ' ')

        # If resource_type is 'all', then get all the resource types
        if 'all' in resource_type:
            resource_type_list = ProjectType.objects.all().values_list('name', flat=True)
        else:
            resource_type_list = resource_type
            resource_type_list = [x.capitalize() for x in resource_type_list]

        # convert the resource_type_list to the respective ids
        resource_type_list = ProjectType.objects.filter(name__in=resource_type_list).values_list('id', flat=True)

        # Default to relevance descending order
        queryset = get_content(resource_type_list, 'relevance', 'desc', search_term)

        return queryset

    def get(self, request, *args, **kwargs):
        """
        Default get method for PublishedProjectSearch that takes in the search_term
        and resource_type as query parameters
        """
        # check if the resource_type requested is valid
        resource_type = self.request.GET.getlist('resource_type', ['all'])
        if not self.check_resource_type(resource_type):
            return Response({'error': 'Invalid resource_type'}, status=400)

        return self.list(request, *args, **kwargs)


class ProjectSHA256Sums(APIView):
    """
    Download SHA256SUMS.txt file for a project.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, project_slug, version):
        project = get_object_or_404(PublishedProject, slug=project_slug, version=version)

        # Check if user has access to the project
        if not can_access_project(project, request.user):
            return Response({"error": "You do not have permission to access this project"}, status=403)

        # Get the path to SHA256SUMS.txt
        sha256sums_path = os.path.join(project.file_root(), 'SHA256SUMS.txt')

        if not os.path.exists(sha256sums_path):
            return Response({"error": "SHA256SUMS.txt not found for this project"}, status=404)

        # Return the file as a download
        response = FileResponse(open(sha256sums_path, 'rb'))
        response['Content-Type'] = 'text/plain'
        response['Content-Disposition'] = 'attachment; filename="SHA256SUMS.txt"'
        return response
