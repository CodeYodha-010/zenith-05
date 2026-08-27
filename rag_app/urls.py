from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('documents/', views.list_documents, name='list_documents'),
    path('document/<int:document_id>/pages/', views.get_document_pages, name='get_document_pages'),
    path('page/<int:page_id>/', views.get_page_content, name='get_page_content'),
    path('search/', views.search_knowledge_base, name='search_knowledge_base'),
    path('ask/', views.ask_question, name='ask_question'),
    path('ask/stream/', views.ask_question_stream, name='ask_question_stream'),

    # Document upload endpoint
    path('upload-document/', views.upload_document, name='upload_document'),

    # Enhanced web search endpoints
    path('enhanced-search/', views.enhanced_web_search, name='enhanced_web_search'),
    path('enhanced-search/stream/', views.enhanced_web_search_stream, name='enhanced_web_search_stream'),
    path('enhanced-search/synthesize/', views.synthesize_web_search, name='synthesize_web_search'),

    path('stats/', views.get_knowledge_base_stats, name='get_knowledge_base_stats'),
    path('clear/', views.clear_knowledge_base, name='clear_knowledge_base'),
    path('suggestions/', views.get_query_suggestions, name='get_query_suggestions'),
]
