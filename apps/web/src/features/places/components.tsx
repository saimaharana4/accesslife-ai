"use client";
import { Dialog, Heading, Modal, ModalOverlay } from "react-aria-components";
import {
  X,
  ExternalLink,
  ArrowUpRight,
  MapPin,
  Accessibility,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import type { Place, Evidence } from "@/lib/api/client";
export function EvidenceDialog({
  place,
  records,
  onClose,
}: {
  place: Place | null;
  records: Evidence[];
  onClose: () => void;
}) {
  return (
    <ModalOverlay
      isOpen={!!place}
      onOpenChange={(open) => !open && onClose()}
      isDismissable
      className="modal-overlay"
    >
      <Modal className="modal">
        <Dialog className="dialog">
          <div className="dialog-top">
            <div>
              <p className="eyebrow">THE INFORMATION BEHIND YOUR PLAN</p>
              <Heading slot="title">{place?.name}</Heading>
            </div>
            <Button
              className="icon ghost"
              aria-label="Close evidence"
              onPress={onClose}
            >
              <X size={22} />
            </Button>
          </div>
          <p>
            Venue statements are evidence, not an independent inspection.
            Approximate map locations do not identify accessible entrances.
          </p>
          {place?.facts.map((f) => (
            <section className="source-fact" key={f.feature}>
              <h3>{f.feature.replaceAll("_", " ")}</h3>
              <span
                className={`badge ${f.status === "confirmed" && !f.stale ? "good" : "warn"}`}
              >
                {f.stale ? "Stale" : f.status}
              </span>
              {(f.evidence_ids ?? []).map((id) => {
                const record = records.find((e) => e.id === id);
                return record ? (
                  <div key={id}>
                    <p>{record.claim}</p>
                    <p className="meta">
                      Retrieved{" "}
                      {new Date(record.retrieved_at).toLocaleDateString()} ·
                      Source update date unknown
                    </p>
                    <a
                      href={record.source_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Official source <ExternalLink size={14} />
                    </a>
                  </div>
                ) : (
                  <p key={id}>
                    Open the official venue page to review the source.
                  </p>
                );
              })}
              {!(f.evidence_ids ?? []).length && (
                <p>
                  No feature-level evidence has been recorded. This does not
                  mean the venue is inaccessible.
                </p>
              )}
            </section>
          ))}
          <a
            className="button secondary"
            href={place?.source_url}
            target="_blank"
            rel="noreferrer"
          >
            Visit official venue website <ArrowUpRight size={16} />
          </a>
        </Dialog>
      </Modal>
    </ModalOverlay>
  );
}

export function PlaceCard({
  place,
  index,
  selected,
  onSelect,
  onEvidence,
}: {
  place: Place;
  index: number;
  selected: boolean;
  onSelect: () => void;
  onEvidence: () => void;
}) {
  const known = place.facts.filter(
    (f) => f.status === "confirmed" && !f.stale,
  ).length;
  return (
    <article className={`place-card ${selected ? "active" : ""}`}>
      <div className={`place-art art-${index % 3}`} aria-hidden="true">
        <div className="arch" />
        <span>
          {place.city_id.replace("new-york", "NEW YORK").toUpperCase()}
        </span>
        <span className="art-number">0{index + 1}</span>
      </div>
      <div className="place-content">
        <div className="card-kicker">
          <span>{place.category}</span>
          <span>
            <MapPin size={13} /> Venue location
          </span>
        </div>
        <h3>
          <button className="title-button" onClick={onSelect}>
            {place.name}
          </button>
        </h3>
        <p>{place.description}</p>
        <div className="fact-row">
          <Accessibility size={17} />
          <span>
            {known
              ? `${known} documented feature${known > 1 ? "s" : ""}`
              : "Access details need checking"}
          </span>
        </div>
        <div className="tag-row">
          {place.interests.slice(0, 3).map((tag) => (
            <span className="tag" key={tag}>
              {tag}
            </span>
          ))}
        </div>
        <div className="card-bottom">
          <span className="meta">Route not verified</span>
          <Button className="text-button" onPress={onEvidence}>
            View evidence <ArrowUpRight size={16} />
          </Button>
        </div>
      </div>
    </article>
  );
}
