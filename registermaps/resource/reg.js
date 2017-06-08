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
	var base = getQueryVariable("base");
	var parent = getQueryVariable("parent");
	
	if (base) {
		// Offset any nodes in an offset span.
		var nodes = document.getElementsByClassName('offset');
		var baseint = parseInt(base)
		var dooffset;
		if (isNaN(baseint)) {
			dooffset = function(offset) {
				return base + '+' + offset;
			}
		} else {
			dooffset = function(offset) {
				return (baseint + parseInt(offset, 16)).toString(16)
			}
		}
		for (var i=0, node; node=nodes[i]; i++) {
			node.textContent = dooffset(node.textContent);
		}
	}
		
	if (parent) {
		var bc = document.getElementById('breadcrumbs');
		var a = document.createElement('A');
		a.href = parent + '.html';
		a.textContent = parent;
		bc.appendChild(a);
	}
}
