import { useEffect } from 'react'
import L from 'leaflet'
import {
  Circle,
  CircleMarker,
  MapContainer,
  Marker,
  Popup,
  TileLayer,
  useMap,
  useMapEvents,
} from 'react-leaflet'
import 'leaflet/dist/leaflet.css'

const proposedSiteIcon = L.divIcon({
  className: 'proposed-map-icon',
  html: '<span></span>',
  iconSize: [24, 24],
  iconAnchor: [12, 12],
})

function MapInteractions({ selectedSite, onLocationChange }) {
  const map = useMap()
  useMapEvents({
    click(event) {
      onLocationChange({ lat: event.latlng.lat, lon: event.latlng.lng })
    },
  })

  useEffect(() => {
    map.flyTo([selectedSite.lat, selectedSite.lon], Math.max(map.getZoom(), 13), {
      duration: 0.45,
    })
  }, [map, selectedSite.lat, selectedSite.lon])

  return null
}

export function MapView({
  candidates,
  selectedSite,
  onLocationChange,
  onCandidateSelect,
}) {
  return (
    <div className="map-frame">
      <MapContainer center={[selectedSite.lat, selectedSite.lon]} zoom={13} scrollWheelZoom>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <MapInteractions selectedSite={selectedSite} onLocationChange={onLocationChange} />
        <Circle
          center={[selectedSite.lat, selectedSite.lon]}
          radius={1_000}
          pathOptions={{ color: '#8ca7a1', weight: 1.5, fillColor: '#a9c3bd', fillOpacity: 0.12 }}
        />
        <Circle
          center={[selectedSite.lat, selectedSite.lon]}
          radius={500}
          pathOptions={{ color: '#28766c', weight: 1.5, fillColor: '#4d9a89', fillOpacity: 0.18 }}
        />
        <Marker
          position={[selectedSite.lat, selectedSite.lon]}
          icon={proposedSiteIcon}
          draggable
          eventHandlers={{
            dragend(event) {
              const point = event.target.getLatLng()
              onLocationChange({ lat: point.lat, lon: point.lng })
            },
          }}
        >
          <Popup>Proposed café location</Popup>
        </Marker>
        {candidates.map((candidate) => (
          <CircleMarker
            key={candidate.id}
            center={[candidate.lat, candidate.lon]}
            radius={7}
            pathOptions={{
              color: '#fff',
              weight: 2,
              fillColor: '#d18b54',
              fillOpacity: 1,
            }}
            eventHandlers={{ click: () => onCandidateSelect(candidate) }}
          >
            <Popup>
              <strong>{candidate.name}</strong><br />
              Illustrative benchmark input<br />
              Competitors: {candidate.competitor_count} · Anchors: {candidate.anchor_count}<br />
              Rent: ₹{candidate.avg_rent_per_sqft}/sq ft
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>
      <span className="map-coordinates">
        {Math.abs(selectedSite.lat).toFixed(4)}° {selectedSite.lat >= 0 ? 'N' : 'S'} · {Math.abs(selectedSite.lon).toFixed(4)}° {selectedSite.lon >= 0 ? 'E' : 'W'}
      </span>
    </div>
  )
}
