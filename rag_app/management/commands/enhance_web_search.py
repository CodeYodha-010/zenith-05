"""
Enhance web search capabilities with multi-source search and intelligent ranking.

Usage:
    python manage.py enhance_web_search --query "What is the wheat export quota?"
    python manage.py enhance_web_search --query "HS code for electronics" --region us
    python manage.py enhance_web_search --query "Export procedure for pharmaceuticals" --region india
    python manage.py enhance_web_search --stats
    python manage.py enhance_web_search --clear-cache
"""

import argparse
import json
import logging
from typing import Optional

from django.core.management.base import BaseCommand

from rag_app.services.query_transformer import get_query_transformer
from rag_app.services.web_search_enhanced import get_enhanced_web_search_service
from rag_app.services.result_synthesizer import get_result_synthesizer
from rag_app.utils.web_search_utils import (
    get_web_search_metrics,
    get_web_search_validator,
    reset_web_search_cache
)

logger = logging.getLogger('rag_pipeline')


class Command(BaseCommand):
    help = 'Enhance web search capabilities with advanced search strategies'

    def add_arguments(self, parser):
        parser.add_argument(
            '--query',
            type=str,
            help='Query to enhance and search'
        )

        parser.add_argument(
            '--region',
            type=str,
            choices=['india', 'us', 'eu'],
            help='Region to focus search on'
        )

        parser.add_argument(
            '--query-type',
            type=str,
            default='general',
            choices=['hs_code', 'duty_rate', 'export_procedure', 'import_procedure',
                    'regulation', 'quota', 'license', 'certificate', 'sanitary', 'general'],
            help='Type of query for better domain selection'
        )

        parser.add_argument(
            '--output',
            type=str,
            default='output',
            help='Output file for results (JSON)'
        )

        parser.add_argument(
            '--stats',
            action='store_true',
            help='Show web search metrics statistics'
        )

        parser.add_argument(
            '--clear-cache',
            action='store_true',
            help='Clear web search cache'
        )

        parser.add_argument(
            '--no-synthesize',
            action='store_true',
            help='Skip result synthesis (show raw results only)'
        )

    def handle(self, *args, **options):
        """Handle the command execution."""

        # Show statistics if requested
        if options['stats']:
            self.show_statistics()
            return

        # Clear cache if requested
        if options['clear_cache']:
            reset_web_search_cache()
            self.stdout.write(self.style.SUCCESS('✅ Web search cache cleared'))
            return

        # Get query from arguments or interactive input
        query = options['query']

        if not query:
            self.stdout.write(self.style.WARNING('\n📝 Interactive Query Input\n'))
            query = input('Enter your query: ').strip()
            if not query:
                self.stdout.write(self.style.ERROR('❌ Query cannot be empty'))
                return

        # Get query type
        query_type = options['query_type']

        # Get region
        region = options['region']

        self.stdout.write(self.style.SUCCESS(f'\n🚀 ENHANCED WEB SEARCH\n'))
        self.stdout.write(self.style.WARNING(f'Query: {query}\n'))
        self.stdout.write(self.style.WARNING(f'Region: {region or "All regions"}\n'))
        self.stdout.write(self.style.WARNING(f'Query Type: {query_type}\n\n'))

        # Execute search
        try:
            # Get services
            transformer = get_query_transformer()
            enhanced_search = get_enhanced_web_search_service()
            synthesizer = get_result_synthesizer()

            # Transform query
            best_query, variations = transformer.enhance_query_for_web_search(
                query, region, max_variations=3
            )

            self.stdout.write(self.style.SUCCESS(f'✅ Query Enhanced\n'))
            self.stdout.write(self.style.WARNING(f'Best Query: {best_query}\n'))
            self.stdout.write(self.style.WARNING(f'Variations:\n'))
            for i, var in enumerate(variations[:3], 1):
                self.stdout.write(self.style.WARNING(f'  {i}. {var}\n'))

            # Perform enhanced search
            search_response = enhanced_search.multi_source_search(
                query=best_query,
                region=region,
                query_type=query_type,
                max_results=15
            )

            self.stdout.write(self.style.SUCCESS(f'✅ Search Complete\n'))
            self.stdout.write(self.style.WARNING(f'Total Results: {search_response["total_results"]}\n'))

            # Skip synthesis if requested
            if not options['no_synthesize']:
                # Synthesize results
                synthesis_response = synthesizer.synthesize_results(
                    search_response, query
                )

                self.stdout.write(self.style.SUCCESS(f'✅ Synthesis Complete\n'))
                self.stdout.write(self.style.WARNING(f'Synthesized Results: {synthesis_response["synthesized_count"]}\n'))
                self.stdout.write(self.style.WARNING(f'Confidence: {synthesis_response["overall_confidence"]:.0%}\n'))

                # Display synthesized results
                self.stdout.write(self.style.SUCCESS('\n📚 SYNTHESIZED RESULTS\n'))
                self.stdout.write(self.style.WARNING('=' * 80 + '\n'))

                for source in synthesis_response['synthesized_results']:
                    self.stdout.write(
                        self.style.WARNING(f'SOURCE {source["source_id"]} [{source["source_type"].upper()}]\n')
                    )
                    self.stdout.write(self.style.WARNING(f'   Domain: {source["domain"]}\n'))
                    self.stdout.write(self.style.WARNING(f'   Title: {source["title"]}\n'))
                    self.stdout.write(self.style.WARNING(f'   Score: {source["final_score"]:.2f}\n'))
                    self.stdout.write(self.style.WARNING(f'   Content:\n'))
                    self.stdout.write(self.style.WARNING(f'   {source["synthesized_content"]}\n'))
                    self.stdout.write(self.style.WARNING('=' * 80 + '\n\n'))

                # Create LLM context
                llm_context = synthesizer.create_llm_context(
                    synthesis_response, query
                )

                # Save to file if output specified
                if options['output'] != 'output':
                    output_file = f"{options['output']}.json"
                    with open(output_file, 'w') as f:
                        json.dump({
                            'query': query,
                            'best_query': best_query,
                            'synthesized_context': llm_context
                        }, f, indent=2)
                    self.stdout.write(
                        self.style.SUCCESS(f'✅ LLM Context saved to {output_file}\n')
                    )
            else:
                # Show raw results
                self.stdout.write(self.style.SUCCESS('\n📊 RAW SEARCH RESULTS\n'))
                for i, result in enumerate(search_response['results'][:5], 1):
                    self.stdout.write(
                        self.style.WARNING(f'{i}. {result["title"]}\n')
                    )
                    self.stdout.write(self.style.WARNING(f'   URL: {result["url"]}\n'))
                    self.stdout.write(self.style.WARNING(f'   Score: {result["relevance_score"]:.2f}\n'))
                    self.stdout.write(self.style.WARNING(f'   Domain: {result["domain"]}\n\n'))

        except Exception as e:
            logger.error(f"❌ Error: {e}", exc_info=True)
            self.stdout.write(self.style.ERROR(f'\n❌ Error: {str(e)}\n'))

        # Show metrics
        metrics = get_web_search_metrics()
        summary = metrics.get_summary()

        self.stdout.write(self.style.SUCCESS('\n📈 SEARCH METRICS\n'))
        self.stdout.write(self.style.WARNING(f'Total Queries: {summary["total_queries"]}\n'))
        self.stdout.write(self.style.WARNING(f'Success Rate: {summary["success_rate"]:.1%}\n'))
        self.stdout.write(self.style.WARNING(f'Avg Results/Query: {summary["avg_results_per_query"]:.1f}\n'))
        self.stdout.write(self.style.WARNING(f'Avg Search Time: {summary["avg_search_time"]:.2f}s\n'))

    def show_statistics(self):
        """Show web search statistics."""
        metrics = get_web_search_metrics()
        stats = metrics.get_statistics()

        self.stdout.write(self.style.SUCCESS('\n📊 WEB SEARCH STATISTICS\n'))
        self.stdout.write(self.style.WARNING('=' * 80 + '\n'))

        # Overall metrics
        self.stdout.write(self.style.WARNING('OVERALL METRICS\n'))
        self.stdout.write(self.style.WARNING(f'Total Queries: {stats["metrics"]["total_queries"]}\n'))
        self.stdout.write(self.style.WARNING(f'Success Rate: {stats["metrics"]["success_rate"]:.1%}\n'))
        self.stdout.write(self.style.WARNING(f'Total Results: {stats["metrics"]["total_results"]}\n'))
        self.stdout.write(self.style.WARNING(f'Avg Results/Query: {stats["average_metrics"]["avg_results"]:.1f}\n'))
        self.stdout.write(self.style.WARNING(f'Avg Search Time: {stats["average_metrics"]["avg_time"]:.2f}s\n'))
        self.stdout.write(self.style.WARNING(f'Avg Confidence: {stats["average_metrics"]["avg_confidence"]:.2f}\n'))

        # Region usage
        self.stdout.write(self.style.WARNING('\nREGION USAGE\n'))
        for region, count in sorted(stats["metrics"]["region_usage"].items()):
            self.stdout.write(self.style.WARNING(f'  {region}: {count} queries\n'))

        # Query type distribution
        self.stdout.write(self.style.WARNING('\nQUERY TYPE DISTRIBUTION\n'))
        for qtype, count in sorted(stats["metrics"]["query_type_distribution"].items()):
            self.stdout.write(self.style.WARNING(f'  {qtype}: {count} queries\n'))

        self.stdout.write(self.style.WARNING('=' * 80 + '\n'))
