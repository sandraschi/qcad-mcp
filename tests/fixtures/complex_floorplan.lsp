;; complex_floorplan.lsp — multi-step architectural drawing
;; Draws outer walls, inner wall, door arc, text labels
(defun c:tiny-house ()
  ;; Outer walls
  (command "_LINE" (list 0 0) (list 8000 0) "")
  (command "_LINE" (list 8000 0) (list 8000 6000) "")
  (command "_LINE" (list 8000 6000) (list 0 6000) "")
  (command "_LINE" (list 0 6000) (list 0 0) "")
  ;; Inner wall (divider)
  (command "_LINE" (list 4000 0) (list 4000 6000) "")
  ;; Column
  (command "_CIRCLE" (list 2000 3000) 150)
  ;; Door arc (south wall, left room)
  (command "_ARC" (list 1000 0) (list 1000 900) (list 1900 0))
  ;; Room labels
  (command "_TEXT" (list 2000 5400) 250 0 "Living Room")
  (command "_TEXT" (list 6000 5400) 250 0 "Bedroom")
  ;; Dimensions
  (command "_DIMLINEAR" (list 0 6200) (list 8000 6200) (list 4000 6500))
  (command "_DIMLINEAR" (list 8200 0) (list 8200 6000) (list 8500 3000))
  (princ "\nTiny house plan complete.")
)
(c:tiny-house)
