import csv
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from routing.models import FuelStation
from routing.services.cities import US_STATES, lookup_city


class Command(BaseCommand):
    help = "Load the fuel price CSV into the database, attaching offline (city-level) coordinates."

    def add_arguments(self, parser):
        parser.add_argument("--csv", default=str(settings.FUEL_PRICES_CSV))

    def handle(self, *args, **options):
        stations = {}
        skipped_non_us = unmatched = 0
        with open(options["csv"], newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                state = row["State"].strip().upper()
                if state not in US_STATES:
                    skipped_non_us += 1
                    continue
                coords = lookup_city(row["City"], state)
                if coords is None:
                    unmatched += 1
                    self.stderr.write(f"No coordinates for {row['City']}, {state}")
                    continue
                opis_id = int(row["OPIS Truckstop ID"])
                price = Decimal(row["Retail Price"]).quantize(Decimal("0.001"))
                # The CSV repeats some truck stops; keep the cheapest listing per OPIS id.
                if opis_id in stations and stations[opis_id].retail_price <= price:
                    continue
                stations[opis_id] = FuelStation(
                    opis_id=opis_id,
                    name=row["Truckstop Name"].strip(),
                    address=row["Address"].strip(),
                    city=row["City"].strip(),
                    state=state,
                    rack_id=int(row["Rack ID"]) if row["Rack ID"].strip() else None,
                    retail_price=price,
                    latitude=coords[0],
                    longitude=coords[1],
                )

        with transaction.atomic():
            FuelStation.objects.all().delete()
            FuelStation.objects.bulk_create(stations.values(), batch_size=1000)

        self.stdout.write(self.style.SUCCESS(
            f"Loaded {len(stations)} US stations "
            f"(skipped {skipped_non_us} non-US rows, {unmatched} without coordinates)."
        ))
