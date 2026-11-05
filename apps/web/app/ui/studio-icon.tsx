const paths = {
  roles: "M8 6V4h8v2M4 7h16v13H4zM4 12h16M10 12v3h4v-3",
  privacy: "m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Zm-3 9 2 2 4-4",
  accounts:
    "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M16 4a4 4 0 0 1 0 8M22 21v-2a4 4 0 0 0-3-3.87M13 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z",
  plus: "M12 5v14M5 12h14",
  search: "M21 21l-4.4-4.4M18 10.5a7.5 7.5 0 1 1-15 0 7.5 7.5 0 0 1 15 0Z",
  arrow: "M5 12h14m-5-5 5 5-5 5",
  lock: "M7 10V7a5 5 0 0 1 10 0v3M5 10h14v11H5zM12 14v3",
} as const;

/** Small decorative line icons; action names always come from visible text. */
export function StudioIcon({ name }: { name: keyof typeof paths }) {
  return (
    <svg
      aria-hidden="true"
      className="studio-icon"
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={paths[name]} />
    </svg>
  );
}
