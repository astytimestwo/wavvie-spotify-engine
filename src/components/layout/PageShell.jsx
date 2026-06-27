import { AnimatePresence, motion } from "framer-motion";
import { Sidebar } from "./Sidebar";

export function PageShell({ page, setPage, user, children }) {
  return (
    <div className="min-h-screen">
      <Sidebar activePage={page} onPageChange={setPage} user={user} />
      <main className="ml-[220px] min-h-screen px-8 py-7">
        <AnimatePresence mode="wait">
          <motion.div
            key={page}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 12 }}
            transition={{ duration: 0.2 }}
          >
            {children}
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  );
}
