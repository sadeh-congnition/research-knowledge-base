from django.db import models


class Project(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Node(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="nodes")
    title = models.CharField(max_length=200)
    content = models.TextField(blank=True)
    links = models.ManyToManyField(
        "self", blank=True, symmetrical=False, related_name="linked_by"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Question(models.Model):
    node = models.ForeignKey(Node, on_delete=models.CASCADE, related_name="questions")
    text = models.TextField()
    answer = models.TextField(blank=True, null=True)
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Question for {self.node.title} - Resolved: {self.is_resolved}"
