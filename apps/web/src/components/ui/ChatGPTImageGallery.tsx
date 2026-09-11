import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ExternalLink, X, ChevronLeft, ChevronRight, Images } from 'lucide-react';

export interface GalleryImage {
  id?: string;
  title: string;
  imageUrl: string;
  thumbnailUrl?: string;
  pageUrl?: string;
  source?: string;
}

interface Props {
  images: GalleryImage[];
  onReuseAsReference?: (img: GalleryImage) => void;
}

export function ChatGPTImageGallery({ images, onReuseAsReference }: Props) {
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);

  const activeImage = lightboxIndex !== null ? images[lightboxIndex] : null;

  const handleNext = useCallback((e?: React.MouseEvent) => {
    e?.stopPropagation();
    setLightboxIndex((prev) => (prev !== null ? (prev + 1) % images.length : 0));
  }, [images.length]);

  const handlePrev = useCallback((e?: React.MouseEvent) => {
    e?.stopPropagation();
    setLightboxIndex((prev) => (prev !== null ? (prev - 1 + images.length) % images.length : 0));
  }, [images.length]);

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (lightboxIndex === null) return;
    if (e.key === 'Escape') setLightboxIndex(null);
    if (e.key === 'ArrowRight') handleNext();
    if (e.key === 'ArrowLeft') handlePrev();
  }, [lightboxIndex, handleNext, handlePrev]);

  useEffect(() => {
    if (lightboxIndex !== null) {
      window.addEventListener('keydown', handleKeyDown);
      return () => window.removeEventListener('keydown', handleKeyDown);
    }
  }, [lightboxIndex, handleKeyDown]);

  if (!images || images.length === 0) return null;

  const displayImages = images.slice(0, 3);
  const remainingCount = images.length - 3;

  const isSingle = displayImages.length === 1;

  return (
    <>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: isSingle ? 'minmax(260px, 380px)' : `repeat(${Math.min(displayImages.length, 3)}, 1fr)`,
          gap: 8,
          width: '100%',
          marginTop: 10,
          marginBottom: 6,
        }}
      >
        {displayImages.map((img, idx) => {
          const isThird = idx === 2;
          const hasMore = isThird && remainingCount > 0;
          const thumbUrl = img.thumbnailUrl || img.imageUrl;

          return (
            <motion.div
              key={img.id || idx}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => setLightboxIndex(idx)}
              style={{
                position: 'relative',
                height: isSingle ? 380 : 180,
                borderRadius: isSingle ? 18 : 14,
                overflow: 'hidden',
                cursor: 'pointer',
                background: 'var(--bg-surface-hover, #f1f5f9)',
                border: '1px solid var(--border-subtle, rgba(0,0,0,0.08))',
                boxShadow: '0 4px 14px rgba(0,0,0,0.08)',
              }}
            >
              {isSingle && (
                <div
                  style={{
                    position: 'absolute',
                    top: 10,
                    right: 10,
                    background: 'rgba(0, 0, 0, 0.65)',
                    backdropFilter: 'blur(8px)',
                    color: '#ffffff',
                    fontSize: '0.72rem',
                    fontWeight: 700,
                    padding: '3px 10px',
                    borderRadius: 8,
                    border: '1px solid rgba(255, 255, 255, 0.25)',
                    letterSpacing: 0.3,
                    zIndex: 2,
                  }}
                >
                  Preview
                </div>
              )}
              {onReuseAsReference && (
                <button
                  type="button"
                  data-testid={`reuse-ref-${idx}`}
                  title="Reuse as Reference for next turn"
                  onClick={(e) => {
                    e.stopPropagation();
                    onReuseAsReference(img);
                  }}
                  style={{
                    position: 'absolute',
                    bottom: 8,
                    left: 8,
                    zIndex: 3,
                    background: 'rgba(0, 0, 0, 0.75)',
                    backdropFilter: 'blur(6px)',
                    border: '1px solid rgba(255, 255, 255, 0.3)',
                    borderRadius: 6,
                    color: '#ffffff',
                    fontSize: '0.68rem',
                    fontWeight: 650,
                    padding: '3px 8px',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4,
                    cursor: 'pointer',
                  }}
                >
                  <Images size={12} />
                  <span>Reuse Reference</span>
                </button>
              )}
              <img
                src={thumbUrl}
                alt={img.title}
                loading='lazy'
                referrerPolicy='no-referrer'
                style={{
                  width: '100%',
                  height: '100%',
                  objectFit: 'cover',
                  display: 'block',
                }}
                onError={(e) => {
                  const target = e.currentTarget as HTMLImageElement;
                  if (img.imageUrl && target.src !== img.imageUrl) {
                    target.src = img.imageUrl;
                  } else {
                    target.style.display = 'none';
                  }
                }}
              />

              {hasMore ? (
                <div
                  style={{
                    position: 'absolute',
                    inset: 0,
                    background: 'linear-gradient(to top, rgba(0,0,0,0.75) 0%, rgba(0,0,0,0.2) 60%, transparent 100%)',
                    display: 'flex',
                    alignItems: 'flex-end',
                    justifyContent: 'flex-end',
                    padding: 10,
                  }}
                >
                  <span
                    style={{
                      background: 'rgba(0,0,0,0.65)',
                      backdropFilter: 'blur(8px)',
                      color: '#ffffff',
                      fontSize: '0.78rem',
                      fontWeight: 700,
                      padding: '4px 10px',
                      borderRadius: 12,
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 5,
                      border: '1px solid rgba(255,255,255,0.2)',
                    }}
                  >
                    <Images size={13} />
                    +{remainingCount}
                  </span>
                </div>
              ) : (
                <div
                  style={{
                    position: 'absolute',
                    bottom: 0,
                    insetInline: 0,
                    padding: '6px 8px',
                    background: 'linear-gradient(to top, rgba(0,0,0,0.6) 0%, transparent 100%)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                  }}
                >
                  <span
                    style={{
                      fontSize: '0.68rem',
                      fontWeight: 600,
                      color: '#ffffff',
                      textShadow: '0 1px 2px rgba(0,0,0,0.8)',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                  >
                    {img.source || 'Web'}
                  </span>
                </div>
              )}
            </motion.div>
          );
        })}
      </div>

      <AnimatePresence>
        {activeImage && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={() => setLightboxIndex(null)}
            style={{
              position: 'fixed',
              inset: 0,
              zIndex: 9999,
              background: 'rgba(0, 0, 0, 0.88)',
              backdropFilter: 'blur(12px)',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: 24,
            }}
          >
            <div
              onClick={(e) => e.stopPropagation()}
              style={{
                position: 'absolute',
                top: 16,
                right: 20,
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                zIndex: 10,
              }}
            >
              {onReuseAsReference && (
                <button
                  type='button'
                  data-testid="lightbox-reuse-ref-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    onReuseAsReference(activeImage);
                    setLightboxIndex(null);
                  }}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '6px 14px',
                    background: 'rgba(236, 72, 153, 0.4)',
                    border: '1px solid rgba(236, 72, 153, 0.7)',
                    borderRadius: 20,
                    color: '#ffffff',
                    fontSize: '0.8rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    backdropFilter: 'blur(8px)',
                  }}
                >
                  <Images size={14} />
                  <span>Reuse Reference</span>
                </button>
              )}
              {activeImage.pageUrl && (
                <a
                  href={activeImage.pageUrl}
                  target='_blank'
                  rel='noopener noreferrer'
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '6px 14px',
                    background: 'rgba(255, 255, 255, 0.15)',
                    border: '1px solid rgba(255, 255, 255, 0.25)',
                    borderRadius: 20,
                    color: '#ffffff',
                    fontSize: '0.8rem',
                    fontWeight: 600,
                    textDecoration: 'none',
                    backdropFilter: 'blur(8px)',
                  }}
                >
                  <ExternalLink size={14} />
                  Visit Page
                </a>
              )}
              <button
                type='button'
                onClick={() => setLightboxIndex(null)}
                style={{
                  background: 'rgba(255, 255, 255, 0.15)',
                  border: '1px solid rgba(255, 255, 255, 0.25)',
                  borderRadius: '50%',
                  width: 36,
                  height: 36,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#ffffff',
                  cursor: 'pointer',
                }}
              >
                <X size={18} />
              </button>
            </div>

            {images.length > 1 && (
              <>
                <button
                  type='button'
                  onClick={handlePrev}
                  style={{
                    position: 'absolute',
                    left: 20,
                    background: 'rgba(255, 255, 255, 0.12)',
                    border: '1px solid rgba(255, 255, 255, 0.2)',
                    borderRadius: '50%',
                    width: 44,
                    height: 44,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#ffffff',
                    cursor: 'pointer',
                    zIndex: 10,
                  }}
                >
                  <ChevronLeft size={24} />
                </button>
                <button
                  type='button'
                  onClick={handleNext}
                  style={{
                    position: 'absolute',
                    right: 20,
                    background: 'rgba(255, 255, 255, 0.12)',
                    border: '1px solid rgba(255, 255, 255, 0.2)',
                    borderRadius: '50%',
                    width: 44,
                    height: 44,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#ffffff',
                    cursor: 'pointer',
                    zIndex: 10,
                  }}
                >
                  <ChevronRight size={24} />
                </button>
              </>
            )}

            <motion.div
              key={lightboxIndex}
              initial={{ scale: 0.94, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.94, opacity: 0 }}
              transition={{ duration: 0.2 }}
              onClick={(e) => e.stopPropagation()}
              style={{
                maxWidth: '85vw',
                maxHeight: '75vh',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
              }}
            >
              <img
                src={activeImage.imageUrl}
                alt={activeImage.title}
                referrerPolicy='no-referrer'
                onError={(e) => {
                  const target = e.currentTarget as HTMLImageElement;
                  if (activeImage.thumbnailUrl && target.src !== activeImage.thumbnailUrl) {
                    target.src = activeImage.thumbnailUrl;
                  }
                }}
                style={{
                  maxWidth: '100%',
                  maxHeight: '70vh',
                  objectFit: 'contain',
                  borderRadius: 12,
                  boxShadow: '0 20px 50px rgba(0,0,0,0.5)',
                }}
              />
              <div
                style={{
                  marginTop: 12,
                  textAlign: 'center',
                  color: '#ffffff',
                  maxWidth: 600,
                }}
              >
                <div style={{ fontSize: '0.92rem', fontWeight: 600 }}>{activeImage.title}</div>
                {activeImage.source && (
                  <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: 3 }}>
                    Source: {activeImage.source} · {(lightboxIndex || 0) + 1} of {images.length}
                  </div>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
