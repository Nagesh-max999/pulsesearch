import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;
export type IconComponent = (props: IconProps) => React.JSX.Element;

function base(children: React.ReactNode, props: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      {children}
    </svg>
  );
}

export function PulseLogo(props: IconProps) {
  return base(<path d="M3 12h4l2-7 4 14 2-7h6" />, props);
}

export function DashboardIcon(props: IconProps) {
  return base(
    <>
      <rect x="3" y="3" width="7" height="9" rx="1.5" />
      <rect x="14" y="3" width="7" height="5" rx="1.5" />
      <rect x="14" y="12" width="7" height="9" rx="1.5" />
      <rect x="3" y="16" width="7" height="5" rx="1.5" />
    </>,
    props,
  );
}

export function DocumentsIcon(props: IconProps) {
  return base(
    <>
      <path d="M7 3h7l5 5v13a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z" />
      <path d="M14 3v5h5" />
      <path d="M9 13h6M9 17h6" />
    </>,
    props,
  );
}

export function SearchIcon(props: IconProps) {
  return base(
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="m21 21-4.3-4.3" />
    </>,
    props,
  );
}

export function UploadIcon(props: IconProps) {
  return base(
    <>
      <path d="M12 16V4M12 4 7 9M12 4l5 5" />
      <path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
    </>,
    props,
  );
}

export function CheckCircleIcon(props: IconProps) {
  return base(
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="m8.5 12.5 2.5 2.5 4.5-5" />
    </>,
    props,
  );
}

export function ClockIcon(props: IconProps) {
  return base(
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3.5 2" />
    </>,
    props,
  );
}

export function AlertIcon(props: IconProps) {
  return base(
    <>
      <path d="M12 3 2 20h20L12 3Z" />
      <path d="M12 10v4M12 17.5h.01" />
    </>,
    props,
  );
}

export function TrashIcon(props: IconProps) {
  return base(
    <>
      <path d="M4 7h16M9 7V4h6v3M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13" />
      <path d="M10 11v6M14 11v6" />
    </>,
    props,
  );
}

export function ChevronLeftIcon(props: IconProps) {
  return base(<path d="m14 6-6 6 6 6" />, props);
}

export function ChevronRightIcon(props: IconProps) {
  return base(<path d="m10 6 6 6-6 6" />, props);
}

export function LogOutIcon(props: IconProps) {
  return base(
    <>
      <path d="M9 21H5a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h4" />
      <path d="M16 17l5-5-5-5M21 12H9" />
    </>,
    props,
  );
}

export function ZapIcon(props: IconProps) {
  return base(<path d="M13 2 4 14h6l-1 8 9-12h-6l1-8Z" />, props);
}

export function LayersIcon(props: IconProps) {
  return base(
    <>
      <path d="m12 3 9 5-9 5-9-5 9-5Z" />
      <path d="m3 13 9 5 9-5" />
    </>,
    props,
  );
}

export function InboxIcon(props: IconProps) {
  return base(
    <>
      <path d="M4 12h4l2 3h4l2-3h4" />
      <path d="M5.5 5h13l2.5 7v6a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-6l2.5-7Z" />
    </>,
    props,
  );
}

export function SparklesIcon(props: IconProps) {
  return base(
    <>
      <path d="M12 3v4M12 17v4M3 12h4M17 12h4" />
      <path d="m12 7-1.8 3.2L7 12l3.2 1.8L12 17l1.8-3.2L17 12l-3.2-1.8Z" />
    </>,
    props,
  );
}

export function SendIcon(props: IconProps) {
  return base(
    <>
      <path d="m3 11 18-8-8 18-2.5-7.5L3 11Z" />
      <path d="M11.5 12.5 20 4" />
    </>,
    props,
  );
}

export function SpinnerIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" {...props}>
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2.5" opacity="0.2" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  );
}
