from django.core.management.base import BaseCommand

from invoices.services.service_keys import generate_service_api_key


class Command(BaseCommand):
    help = 'Creates a ServiceApiKey for the verified-winners export API and prints the raw key once.'

    def add_arguments(self, parser):
        parser.add_argument('name', type=str)

    def handle(self, *args, **options):
        raw, key = generate_service_api_key(options['name'])
        self.stdout.write(self.style.SUCCESS(f'Created key "{key.name}" (id={key.id}).'))
        self.stdout.write(self.style.WARNING('COPY THIS NOW — it will never be shown again:'))
        self.stdout.write(raw)
