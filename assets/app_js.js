document.addEventListener("keydown", clickButtonFunction);

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
}