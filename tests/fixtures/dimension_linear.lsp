;; dimension_linear.lsp — add linear dimensions
(defun c:dim-walls (pt1 pt2 pt3)
  (command "_DIMLINEAR" pt1 pt2 pt3)
)
(c:dim-walls (list 0 0) (list 5000 0) (list 2500 -500))
