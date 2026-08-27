from django.db import models


class Document(models.Model):
    """Stores metadata about each ingested document."""
    title = models.CharField(max_length=500)
    file_path = models.TextField()
    region = models.CharField(max_length=50, default='india', choices=[
        ('eu', 'European Union'),
        ('india', 'India'),
        ('us', 'United States'),
    ])
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # OCR tracking fields
    is_ocred = models.BooleanField(default=False, help_text="True if any page in this document required OCR")
    ocr_confidence_avg = models.FloatField(null=True, blank=True, help_text="Average OCR confidence score (0.0 to 1.0)")
    
    def __str__(self):
        return f"[{self.region.upper()}] {self.title}"
    
    class Meta:
        ordering = ['-created_at']


class DocumentPage(models.Model):
    """Stores page-level content and LLM-generated summaries."""
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='pages')
    page_number = models.IntegerField()
    original_text = models.TextField()
    summary = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.document.title} - Page {self.page_number}"
    
    class Meta:
        ordering = ['document', 'page_number']
        unique_together = ['document', 'page_number']


class SearchIndex(models.Model):
    """Stores searchable content (summaries and chunks) for BM25 search."""
    page = models.ForeignKey(DocumentPage, on_delete=models.CASCADE, related_name='search_entries')
    content = models.TextField()
    source_type = models.CharField(max_length=20, choices=[
        ('summary', 'Summary'),
        ('chunk', 'Chunk'),
    ])
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Vector Embedding fields for FAISS/cosine search
    embedding = models.JSONField(null=True, blank=True, help_text="Vector embedding stored as a JSON float array")
    embedding_model = models.CharField(max_length=100, blank=True, default='', help_text="Model used to generate the embedding")
    
    # Enhanced metadata fields
    section_title = models.CharField(max_length=500, blank=True, default='', help_text="Header/section this chunk belongs to (e.g., 'Import Procedures')")
    chunk_type = models.CharField(max_length=20, default='text', choices=[
        ('text', 'Text'),
        ('table', 'Table'),
        ('list', 'List'),
    ], help_text="Type of content in this chunk")
    is_ocr_generated = models.BooleanField(default=False, help_text="True if this text came from OCR processing")
    
    # Parent-child chunking fields
    chunk_level = models.CharField(max_length=10, choices=[
        ('parent', 'Parent'),
        ('child', 'Child'),
    ], default='child', help_text="Whether this is a parent (large context) or child (precise retrieval) chunk")
    
    parent_chunk = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, 
                                      related_name='child_chunks', 
                                      help_text="Parent chunk for child entries, None for parent entries")
    
    char_start = models.IntegerField(null=True, blank=True, 
                                      help_text="Character position where this chunk starts in original text")
    
    document_size = models.CharField(max_length=10, choices=[
        ('short', 'Short'),
        ('medium', 'Medium'),
        ('large', 'Large'),
    ], null=True, blank=True, help_text="Size category of the source document")

    # Vector embedding fields for semantic search
    embedding = models.JSONField(null=True, blank=True, help_text="Vector embedding for semantic search")
    embedding_model = models.CharField(max_length=100, null=True, blank=True, help_text="Model used to generate the embedding")

    def __str__(self):
        return f"{self.page} - {self.source_type} ({self.chunk_level})"
    
    class Meta:
        ordering = ['page', 'source_type', 'chunk_level']


class DocumentMetadata(models.Model):
    """
    Rich metadata for each document — enables document-level retrieval.
    
    Instead of searching 10,000+ blind chunks, we can first identify
    which documents are relevant by their topics, commodities, and key facts.
    """
    document = models.OneToOneField(Document, on_delete=models.CASCADE, related_name='metadata')
    
    # Topic tags (comma-separated): "wheat_export,export_procedure,application_process"
    topics = models.TextField(blank=True, default='',
                              help_text="Comma-separated topic tags extracted by LLM")
    
    # Commodity/product tags: "wheat,durum_wheat,grain"
    commodities = models.TextField(blank=True, default='',
                                   help_text="Comma-separated commodities mentioned")
    
    # Referenced regulations: "FTP_2023,Notification_62,Public_Notice_49"
    regulations = models.TextField(blank=True, default='',
                                   help_text="Comma-separated regulations/policies referenced")
    
    # 200-word LLM-generated document summary
    summary = models.TextField(blank=True, default='',
                               help_text="200-word overview of the entire document")
    
    # Key facts as JSON: {"minimum_export_quantity": "10,000 MT", "deadline": "2026-04-15"}
    key_facts = models.TextField(blank=True, default='',
                                 help_text="JSON dict of key facts extracted by LLM")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Metadata: {self.document.title[:40]}"
    
    class Meta:
        ordering = ['-created_at']


class FactIndex(models.Model):
    """
    Structured facts extracted from individual pages/chunks.
    
    This is the key to answering hard questions. When a user asks
    "what's the minimum quantity for wheat exports", we don't search
    for keywords — we query: FactIndex where subject='wheat_export' 
    AND fact_type='quantity_limit' → returns value='10,000 MT'.
    
    Each fact is linked to its source chunk and page for verification.
    """
    page = models.ForeignKey(DocumentPage, on_delete=models.CASCADE, related_name='facts')
    chunk = models.ForeignKey(SearchIndex, on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='facts',
                              help_text="The SearchIndex chunk this fact was extracted from")
    
    # Type of fact
    fact_type = models.CharField(max_length=30, choices=[
        ('quantity_limit', 'Quantity Limit'),
        ('deadline', 'Deadline'),
        ('requirement', 'Requirement'),
        ('penalty', 'Penalty'),
        ('exemption', 'Exemption'),
        ('procedure_step', 'Procedure Step'),
        ('fee_rate', 'Fee or Rate'),
        ('eligibility', 'Eligibility Criteria'),
        ('document_type', 'Document Type'),
        ('other', 'Other'),
    ], default='other', help_text="Category of this fact")
    
    # What subject this fact is about: "wheat_export", "REACH_registration", etc.
    subject = models.CharField(max_length=200, default='',
                               help_text="Topic/subject of this fact (e.g., 'wheat_export')")
    
    # The actual value: "10,000 MT", "30 days", "required", etc.
    value = models.TextField(help_text="The extracted fact value")
    
    # Conditions/qualifiers: "applies to applications below this threshold"
    condition = models.TextField(blank=True, default='',
                                 help_text="Conditions or qualifiers for this fact")
    
    # The exact source text for verification
    raw_text = models.TextField(help_text="Exact sentence/paragraph the fact came from")
    
    # Confidence from extraction LLM (0.0-1.0)
    confidence = models.FloatField(default=0.0, help_text="LLM confidence in this extraction (0.0-1.0)")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"[{self.fact_type}] {self.subject}: {self.value[:50]}"
    
    class Meta:
        ordering = ['-confidence', '-created_at']
        indexes = [
            models.Index(fields=['fact_type', 'subject']),
            models.Index(fields=['page', 'fact_type']),
        ]
