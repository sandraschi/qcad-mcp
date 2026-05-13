;; draw_line.lsp — basic LINE command
(defun c:draw-line ()
  (command "_LINE" (list 0 0) (list 100 50) "")
)
(c:draw-line)
