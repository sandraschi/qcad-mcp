;; layer_create.lsp — create layers with color
(defun c:setup-layers ()
  (command "_LAYER" "N" "Walls" "C" "1" "Walls" "")
  (command "_LAYER" "N" "Doors" "C" "3" "Doors" "")
  (command "_LAYER" "N" "Furniture" "C" "5" "Furniture" "")
)
(c:setup-layers)
