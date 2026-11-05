"""Tiny in-memory stand-in for the supabase-py query builder (enough for these tests)."""
import itertools

class Res:
    def __init__(self, data): self.data = data

class Q:
    def __init__(self, db, name): self.db, self.name, self.op, self.f, self.gte_f, self.in_f, self.lim = db, name, "select", {}, {}, {}, None
    def select(self, *_): self.op = "select"; return self
    def insert(self, rows): self.op, self.rows = "insert", rows if isinstance(rows, list) else [rows]; return self
    def upsert(self, row): self.op, self.rows = "upsert", [row]; return self
    def delete(self): self.op = "delete"; return self
    def eq(self, k, v): self.f[k] = v; return self
    def gte(self, k, v): self.gte_f[k] = v; return self
    def in_(self, k, vs): self.in_f[k] = set(vs); return self
    def order(self, k, desc=False): self.ord = (k, desc); return self
    def limit(self, n): self.lim = n; return self
    def _match(self, r):
        return (all(r.get(k) == v for k, v in self.f.items())
                and all(str(r.get(k)) >= v for k, v in self.gte_f.items())
                and all(r.get(k) in vs for k, vs in self.in_f.items()))
    def execute(self):
        t = self.db.tables.setdefault(self.name, [])
        if self.op == "insert":
            out = []
            for r in self.rows:
                r = {"id": f"{self.name}-{next(self.db.ids)}", "created_at": "2026-10-10T10:00:00", **r}
                t.append(r); out.append(r)
            return Res(out)
        if self.op == "upsert":
            r = self.rows[0]
            for x in t:
                if x["id"] == r["id"]: x.update(r); return Res([x])
            t.append(dict(r)); return Res([r])
        if self.op == "delete":
            t[:] = [r for r in t if not self._match(r)]; return Res([])
        rows = [dict(r) for r in t if self._match(r)]
        if hasattr(self, "ord"): rows.sort(key=lambda r: str(r.get(self.ord[0])), reverse=self.ord[1])
        return Res(rows[: self.lim] if self.lim else rows)

class FakeDB:
    def __init__(self): self.tables, self.ids = {}, itertools.count(1)
    def table(self, n): return Q(self, n)
