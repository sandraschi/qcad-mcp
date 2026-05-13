;; array_grid.lsp — repeat loop for grid generation
(defun c:draw-grid (/ x y)
  (setq x 0)
  (repeat 5
    (setq y 0)
    (repeat 4
      (command "_LINE" (list x y) (list (+ x 100) y) "")
      (command "_LINE" (list x y) (list x (+ y 100)) "")
      (setq y (+ y 100))
    )
    (setq x (+ x 100))
  )
)
(c:draw-grid)
