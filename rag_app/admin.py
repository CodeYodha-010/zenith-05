from django.contrib import admin
from .models import Document, DocumentPage, SearchIndex


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'region', 'processed_at', 'created_at']
    list_filter = ['region', 'processed_at']
    search_fields = ['title', 'file_path']
    readonly_fields = ['created_at']


@admin.register(DocumentPage)
class DocumentPageAdmin(admin.ModelAdmin):
    list_display = ['document', 'page_number', 'summary_preview', 'created_at']
    list_filter = ['document__region']
    search_fields = ['document__title', 'original_text', 'summary']
    readonly_fields = ['created_at']
    
    def summary_preview(self, obj):
        return obj.summary[:100] + '...' if len(obj.summary) > 100 else obj.summary
    summary_preview.short_description = 'Summary Preview'


@admin.register(SearchIndex)
class SearchIndexAdmin(admin.ModelAdmin):
    list_display = ['page', 'source_type', 'content_preview', 'created_at']
    list_filter = ['source_type', 'page__document__region']
    search_fields = ['content']
    readonly_fields = ['created_at']
    
    def content_preview(self, obj):
        return obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
    content_preview.short_description = 'Content Preview'