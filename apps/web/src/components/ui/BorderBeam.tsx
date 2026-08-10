import { BorderBeam as BaseBorderBeam } from "border-beam";

export interface BorderBeamProps {
  children?: React.ReactNode;
  className?: string;
}

export function BorderBeam({ children, className = "" }: BorderBeamProps) {
  return (
    <BaseBorderBeam className={className}>
      {children}
    </BaseBorderBeam>
  );
}

export default BorderBeam;
