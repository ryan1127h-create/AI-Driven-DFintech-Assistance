import { Home } from "lucide-react";
import { PageHeader } from "../PageParts";
import { Card, Badge } from "../../ui";

export function HousingPage() {
  return (
    <div>
      <PageHeader icon={Home} title="Housing" subtitle="On-campus and off-campus accommodation options" />
      <div className="grid sm:grid-cols-2 gap-4">
        {[
          { name: "UTown Residences", type: "On-campus", price: "S$650-1,100/mo", distance: "5 min walk" },
          { name: "PGPR (Prince George's Park)", type: "On-campus", price: "S$400-800/mo", distance: "10 min walk" },
          { name: "Clementi Condo (shared)", type: "Off-campus", price: "S$900-1,400/mo", distance: "15 min MRT" },
          { name: "Queenstown HDB (room)", type: "Off-campus", price: "S$700-1,000/mo", distance: "20 min MRT" },
        ].map((h, i) => (
          <Card key={i}>
            <h3 className="font-display text-base font-semibold text-app-primary">{h.name}</h3>
            <p className="text-sm text-app-muted mt-1">{h.type}</p>
            <div className="mt-3 flex items-center justify-between">
              <span className="text-sm font-medium text-emerald2-400">{h.price}</span>
              <Badge color="ink">{h.distance}</Badge>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
