;; draw_rect_defun.lsp — defun with parameters, RECTANG
(defun draw-rect (w h)
  (command "_RECTANG" (list 0 0) (list w h))
)
(draw-rect 100 80)
