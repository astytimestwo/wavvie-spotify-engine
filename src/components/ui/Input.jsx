export function Input({ label, className = "", ...props }) {
  return (
    <label className={`block ${className}`}>
      {label ? <span className="label-caps mb-2 block">{label}</span> : null}
      <input
        className="h-12 w-full rounded-[14px] border border-mist bg-void/70 px-4 text-sm text-snow outline-none transition placeholder:text-ghost focus:border-iris focus:shadow-iris"
        {...props}
      />
    </label>
  );
}
