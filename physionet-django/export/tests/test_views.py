import os
import tempfile

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from project.models import PublishedProject
from user.models import User


class ProjectSHA256SumsTests(TestCase):
    def setUp(self):
        # Create test user
        self.user = User.objects.create(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.unauthorized_user = User.objects.create(
            username='unauthorized',
            email='unauthorized@example.com',
            password='testpass123'
        )

        # Create test project
        self.project = PublishedProject.objects.create(
            slug='test-project',
            version='1.0.0',
            title='Test Project',
            resource_type=0,
            publish_datetime='2024-01-01T00:00:00Z'
        )

        # Create temporary directory for project files
        self.temp_dir = tempfile.mkdtemp()
        self.project.file_root = lambda: self.temp_dir

        # Create test SHA256SUMS.txt file
        self.sha256sums_path = os.path.join(self.temp_dir, 'SHA256SUMS.txt')
        with open(self.sha256sums_path, 'w') as f:
            f.write('test content')

        # Setup API client
        self.client = APIClient()

    def tearDown(self):
        # Clean up temporary directory
        if os.path.exists(self.temp_dir):
            for file in os.listdir(self.temp_dir):
                os.remove(os.path.join(self.temp_dir, file))
            os.rmdir(self.temp_dir)

    def test_unauthorized_access(self):
        """Test that unauthorized users cannot access SHA256SUMS.txt"""
        url = reverse(
            'published_project_sha256sums',
            kwargs={
                'project_slug': self.project.slug,
                'version': self.project.version
            }
        )

        # Try without authentication
        response = self.client.get(url)
        self.assertEqual(response.status_code, 401)

        # Try with unauthorized user
        self.client.force_authenticate(user=self.unauthorized_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_missing_file(self):
        """Test handling of missing SHA256SUMS.txt file"""
        # Remove the test file
        os.remove(self.sha256sums_path)

        url = reverse(
            'published_project_sha256sums',
            kwargs={
                'project_slug': self.project.slug,
                'version': self.project.version
            }
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['error'], 'SHA256SUMS.txt not found for this project')

    def test_successful_download(self):
        """Test successful download of SHA256SUMS.txt"""
        url = reverse(
            'published_project_sha256sums',
            kwargs={
                'project_slug': self.project.slug,
                'version': self.project.version
            }
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/plain')
        self.assertEqual(response['Content-Disposition'], 'attachment; filename="SHA256SUMS.txt"')
        self.assertEqual(response.content.decode(), 'test content')

    def test_nonexistent_project(self):
        """Test handling of nonexistent project"""
        url = reverse(
            'published_project_sha256sums',
            kwargs={
                'project_slug': 'nonexistent',
                'version': '1.0.0'
            }
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
