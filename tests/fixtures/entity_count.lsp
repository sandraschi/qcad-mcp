;; entity_count.lsp — select all entities and count by type
(defun c:count-entities ()
  (setq ss (ssget "X"))
  (if ss
    (progn
      (setq n (sslength ss))
      (princ (strcat "\nTotal entities: " (rtos n 2 0)))
      (princ "\nDone.")
    )
    (princ "\nNo entities found.")
  )
)
(c:count-entities)
