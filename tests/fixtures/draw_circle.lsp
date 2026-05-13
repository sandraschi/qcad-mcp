;; draw_circle.lsp — CIRCLE with center and radius
(defun c:draw-circle ()
  (command "_CIRCLE" (list 50 25) 20)
)
(c:draw-circle)
