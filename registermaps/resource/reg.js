// Javascript support for Component HTML files.

function getQueryVariable(variable)
{
	var query = window.location.search.substring(1);
	var vars = query.split("&");
	for (var i=0;i<vars.length;i++) {
		var pair = vars[i].split("=");
		if (pair[0] == variable) {
			return pair[1];
		}
	}
	return(false);
}

window.onload = function()
{
	base = getQueryVariable("base");
	parent = getQueryVariable("parent");
	
	if (base) {
		// Offset any nodes in an offset span.
		nodes = document.getElementsByClassName('offset');
		baseint = parseInt(base)
		if (isNaN(baseint)) {
			dooffset = function(offset) {
				return base + '+' + offset;
			}
		} else {
			dooffset = function(offset) {
				return baseint + parseInt(offset);
			}
		}
		for (var i=0, node; node=nodes[i]; i++) {
			offset = node.currentText;
			node.currentText = dooffset(offset);
		}
	}
		
	if (parent) {
		bc = document.getElementById('breadcrumbs');
		a = document.createElement('A');
		a.href = parent + '.html';
		a.appendChild(document.createTextNode(parent));
		bc.appendChild(a);
	}
}
