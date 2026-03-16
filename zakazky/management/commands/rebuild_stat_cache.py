import datetime as dt
from django.core.management.base import BaseCommand
from django.utils.timezone import localdate

from ...stats_cache import cache_path, save_cache
from ...stats_snapshot import build_statistiky_context


class Command(BaseCommand):
    help = "Rebuild statistics cache files (snapshot to yesterday) and store as plain context dict."

    def add_arguments(self, parser):
        parser.add_argument("--months", type=int, default=24, help="How many last months to cache.")
        parser.add_argument("--years", type=int, default=5, help="How many last years to cache.")
        parser.add_argument("--include-all", action="store_true", dest="include_all",
                            help="Also cache scope=all.")

    def handle(self, *args, **opts):
        cutoff = localdate() - dt.timedelta(days=1)

        months = int(opts.get("months") or 24)
        years = int(opts.get("years") or 5)
        include_all = bool(opts.get("include_all"))

        def iter_months(start_y: int, start_m: int, count: int):
            y, m = start_y, start_m
            for _ in range(count):
                yield y, m
                m -= 1
                if m == 0:
                    y -= 1
                    m = 12

        # --- MONTH caches
        for y, m in iter_months(cutoff.year, cutoff.month, months):
            ym = f"{y:04d}-{m:02d}"
            ctx = build_statistiky_context("month", ym=ym, cutoff=cutoff)
            ctx["cache_source"] = "cache_file"
            save_cache(cache_path("month", ym=ym), ctx)
            self.stdout.write(self.style.SUCCESS(f"cached month {ym} (cutoff={cutoff.isoformat()})"))

        # --- YEAR caches
        for i in range(years):
            yy = cutoff.year - i
            ctx = build_statistiky_context("year", y=yy, cutoff=cutoff)
            ctx["cache_source"] = "cache_file"
            save_cache(cache_path("year", y=yy), ctx)
            self.stdout.write(self.style.SUCCESS(f"cached year {yy} (cutoff={cutoff.isoformat()})"))

        # --- ALL cache (optional)
        if include_all:
            ctx = build_statistiky_context("all", cutoff=cutoff)
            ctx["cache_source"] = "cache_file"
            save_cache(cache_path("all"), ctx)
            self.stdout.write(self.style.SUCCESS(f"cached all (cutoff={cutoff.isoformat()})"))