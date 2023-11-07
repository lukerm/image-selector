document.addEventListener("keyup", clickButtonFunction);

function clickButtonFunction(event){
  if(event.key == 'ArrowLeft'){
    document.getElementById("move-left").click();
  }
  if(event.key == 'ArrowRight'){
    document.getElementById("move-right").click();
  }
  if(event.key == 'ArrowUp'){
    document.getElementById("move-up").click();
  }
  if(event.key == 'ArrowDown'){
    document.getElementById("move-down").click();
  }
  if(event.key == '='){
    document.getElementById("keep-button").click();
  }
  if(event.key == 'Backspace'){
    document.getElementById("delete-button").click();
  }
  if(event.key == 's'){
    document.getElementById("keep-button").click();
  }
  if(event.key == 'd'){
    document.getElementById("delete-button").click();
  }
  if(event.key == 'g'){
    document.getElementById("group-button").click();
  }
  if(event.key == 'C'){
    document.getElementById("complete-group").click();
  }
  if(event.key == 'Z'){
    document.getElementById("undo-button").click();
  }
  if(event.key == '1'){
    document.getElementById("select-row-upto-1-button").click();
  }
  if(event.key == '2'){
    document.getElementById("select-row-upto-2-button").click();
  }
  if(event.key == '3'){
    document.getElementById("select-row-upto-3-button").click();
  }
  if(event.key == '4'){
    document.getElementById("select-row-upto-4-button").click();
  }
  if(event.key == '5'){
    document.getElementById("select-row-upto-5-button").click();
  }
  if(event.key == '6'){
    document.getElementById("select-row-upto-6-button").click();
  }
  if(event.key == '7'){
    document.getElementById("select-row-upto-7-button").click();
  }
  if(event.key == '8'){
    document.getElementById("select-row-upto-8-button").click();
  }
  if(event.key == '9'){
    document.getElementById("select-row-upto-9-button").click();
  }
  if(event.key == '0'){
    document.getElementById("select-row-upto-1000-button").click();
  }
  if(event.key == 'A'){
    document.getElementById("select-row-upto-1000-button").click();
  }
  if (event.key === 'q') {
    document.getElementById("jump-right-2-cells-button").click();
  }
  if (event.key === 'w') {
    document.getElementById("jump-right-3-cells-button").click();
  }
  if (event.key === 'e') {
    document.getElementById("jump-right-4-cells-button").click();
  }
  if (event.key === 'r') {
    document.getElementById("jump-right-5-cells-button").click();
  }
  if (event.key === 't') {
    document.getElementById("jump-right-6-cells-button").click();
  }
  if (event.key === 'y') {
    document.getElementById("jump-right-7-cells-button").click();
  }
  if (event.key === 'Q') {
    document.getElementById("jump-left-2-cells-button").click();
  }
  if (event.key === 'W') {
    document.getElementById("jump-left-3-cells-button").click();
  }
  if (event.key === 'E') {
    document.getElementById("jump-left-4-cells-button").click();
  }
  if (event.key === 'R') {
    document.getElementById("jump-left-5-cells-button").click();
  }
  if (event.key === 'T') {
    document.getElementById("jump-left-6-cells-button").click();
  }
  if (event.key === 'Y') {
    document.getElementById("jump-left-7-cells-button").click();
  }
}
