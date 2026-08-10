import React from 'react';
import { motion } from 'framer-motion';
import { ArrowRight, Search, Image, Code, BookOpen, RotateCcw } from 'lucide-react';

export interface ActionChip {
  id: string;
  label: string;
  icon?: string;
  disabled?: boolean;
  loading?: boolean;
}

interface ActionChipsProps {
  chips: ActionChip[];
  onChip: (chip: ActionChip) => void;
}

const ICON_MAP: Record<string, React.ElementType> = {
  search: Search,
  image: Image,
  code: Code,
  book: BookOpen,
  retry: RotateCcw,
  default: ArrowRight,
};

export function ActionChips({ chips, onChip }: ActionChipsProps) {
  if (chips.length === 0) return null;

  return (
    <motion.div
      className="action-chips"
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: 0.2 }}
    >
      {chips.map((chip, i) => {
        const IconComponent = ICON_MAP[chip.icon ?? 'default'] ?? ICON_MAP.default;
        return (
          <motion.button
            key={chip.id}
            className="action-chip"
            onClick={() => !chip.disabled && !chip.loading && onChip(chip)}
            disabled={chip.disabled || chip.loading}
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: i * 0.04 + 0.1 }}
            whileHover={!chip.disabled && !chip.loading ? { scale: 1.02, y: -1 } : {}}
            whileTap={!chip.disabled && !chip.loading ? { scale: 0.97 } : {}}
          >
            {chip.loading ? (
              <motion.div
                style={{ width: 12, height: 12, border: '2px solid currentColor', borderTopColor: 'transparent', borderRadius: '50%' }}
                animate={{ rotate: 360 }}
                transition={{ duration: 0.7, repeat: Infinity, ease: 'linear' }}
              />
            ) : (
              <IconComponent size={12} />
            )}
            <span>{chip.label}</span>
          </motion.button>
        );
      })}
    </motion.div>
  );
}

export default ActionChips;
